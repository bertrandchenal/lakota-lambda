import orjson
import gzip
import os
from base64 import b64encode
from pathlib import Path

from chalice import Chalice, Response
from chalice import BadRequestError
from jensen import Registry, Schema
from jensen.utils import logger
from jinja2 import Environment, FileSystemLoader
from numpy import bincount, unique
from numpy.core.defchararray import find

logger.setLevel('CRITICAL')
title = os.environ.get('APP_TITLE', 'Jensen')
db_bucket = os.environ['DB_BUCKET']
app_prefix = os.environ.get('APP_PREFIX', '')
static_prefix = 'static'
registry = Registry('file:///tmp/jensen-cache+s3://' + db_bucket)
lib_path = Path(__file__).parent / 'chalicelib'
tpl_path = lib_path / 'template'
static_path = lib_path / 'static'
env = Environment(loader=FileSystemLoader([tpl_path]))
app = Chalice(app_name='jensen-lambda')
app.api.binary_types.extend(['application/json'])

uplot_options = {
    # 'title': '',
    # 'id': '',
    # 'class': '',
    'width': 900,
    'height': 300,
    'series': [
        {},
        {
            # initial toggled state (optional)
            'show': True,
            'spanGaps': False,
            # in-legend display
            'label': "Value1",
            # series style
            'stroke': "red",
            'width': 1,
            'fill': "rgba(255, 0, 0, 0.3)",
            'dash': [10, 5],
        },
    ],
}


def render_template(name, **kw):
    tpl = env.get_template(name)
    body = tpl.render(**kw, prefix=app_prefix, static=static_prefix)
    return Response(
        body,
        headers={'Content-Type': 'Content-Type: text/html; charset=utf-8'},
        status_code=200)


@app.route('/', methods=['GET', 'HEAD'])
def index():
    logo = (static_path / 'jensen-sm.png').open('rb').read()
    logo = "data:image/png;base64, " + b64encode(logo).decode()
    return render_template('index.html', title=title, b64logo=logo)


@app.route('/static/{filename}', methods=['GET', 'HEAD'])
def static(filename):
    ext = filename.rsplit('.', 1)[1]
    mimes = {
        'css': 'text/css',
        'js': 'text/javascript',
    }
    content_type = mimes.get(ext)
    if content_type is None:
        # Not supported
        raise BadRequestError('Unsupported extension')
    try:
        body = (static_path / filename).open().read()
    except FileNotFoundError:
        raise BadRequestError('File not found')
    return Response(
        body,
        headers={'Content-Type': 'Content-Type: ' + content_type},
        status_code=200)


@app.route('/favicon.ico', methods=['GET', 'HEAD'])
def favico():
    return "" # TODO


@app.route('/search')
def search():
    params = app.current_request.query_params or {}
    patterns = params.get('label-filter', '').split()
    frm = registry.search()
    labels = frm['label']
    for pattern in patterns:
        cond = find(labels, pattern) != -1
        labels = labels[cond]
    return render_template('search-modal.html', labels=labels)


@app.route('/series/{label}', methods=['POST', 'GET'])
def series(label):
    frm = registry.search(label)
    schema = Schema.loads(frm['schema'][0])
    columns = list(schema.columns.keys())[schema.idx_len:]
    return render_template('series.html', label=label, columns=columns)


@app.route('/graph/{label}/{column}')
def graph(label, column):
    params = app.current_request.query_params or {}
    series = registry.get(label)
    schema = series.schema
    inputs = {}

    if schema.idx_len > 1:
        # Prepare aggregation values
        frm = series.read()
        for name, coldef in schema.idx.items():
            if coldef.dt == 'datetime64[s]':
                continue
            values = [''] + sorted(set(frm[name]))
            inputs[name]= [params.get(name, ''), values]

    horizon = {}
    for field in ('__date_start', '__date_stop'):
        horizon[field] = params.get(field, '')

    uri = f'{app_prefix}/read/{label}/{column}'
    if params:
        uri = uri + '?' + '&'.join(f'{n}={v}' for n, v in params.items())
    return render_template(
        'graph.html', uri=uri, label=label, column=column, inputs=inputs, horizon=horizon,
        show_filters=bool(params))


# USE a pure lambda ?
@app.route('/read/{label}/{column}')
def read(label, column):
    series = registry.get(label)
    frm = series.read()
    params = app.current_request.query_params or {}

    # slice timestamp
    frm = frm[params.get("__date_start", None):params.get("__date_stop", None)]

    # Slice other columns
    for col, value in params.items():
        if col not in frm.columns or not value:
            continue
        frm = frm.mask(frm[col] == value)

    # find time dimension
    tdim = None
    for name, coldef in series.schema.idx.items():
        if coldef.dt == 'datetime64[s]':
            tdim = name
            break
    else:
        # No time dimension found
        return

    # Aggregate on time dimension
    if series.schema.idx_len > 1:
        # TODO skip also this step if every index column is filtered
        ts = frm[tdim].astype(int)
        keys, bins = unique(ts, return_inverse=True)
        res = bincount(bins, weights=frm[column])
        data = [keys, res]
    else:
        data = [frm[tdim].astype(int), frm[column]]

    # Build response
    content = orjson.dumps(
        {'data': data, 'options': uplot_options},
        option=orjson.OPT_SERIALIZE_NUMPY)
    payload = gzip.compress(content, compresslevel=1)
    headers = {
        'Content-Type': 'application/json',
        'Content-Encoding': 'gzip'
    }
    return Response(body=payload,
                    status_code=200,
                    headers=headers)
