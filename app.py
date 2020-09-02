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
uri = os.environ['JENSEN_URI']
app_prefix = os.environ.get('APP_PREFIX', '')
static_prefix = 'static'
registry = Registry(uri)

PAGE_LEN = 100_000
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
    columns = [c for c in schema.columns if c not in schema.idx]
    return render_template('series.html', label=label, columns=columns)


@app.route('/graph/{label}/{column}')
@app.route('/graph/{label}/{column}/page/{page}')
def graph(label, column, page=0):
    params = app.current_request.query_params or {}
    series = registry.get(label)
    schema = series.schema
    inputs = {}

    if len(schema.idx) > 1:
        # Prepare aggregation values
        # FIXME pre-filter based on param
        frm = series.limit(10000).frame()
        for name, coldef in schema.idx.items():
            if coldef.dt == 'datetime64[s]':
                continue
            values = [''] + sorted(set(frm[name]))
            inputs[name]= [params.get(name, ''), values]

    ui = {
        'page': 0,
        'start': None,
        'stop': None,
        'page_len': PAGE_LEN,
    }

    for field in ('start', 'stop'):
        key = 'ui.' + field
        value = params.get(key, '')
        ui[field] = value

    page = int(params.get('ui.page', '0'))
    active_btn = app.current_request.headers.get('HX-Active-Element-Value')
    if active_btn:
        page += 1 if active_btn == 'next' else -1
        page = max(page, 0)
        ui['page'] = page

    uri = f'{app_prefix}/read/{label}/{column}'
    if any(ui.values()):
        uri = uri + '?' + '&'.join(f'ui.{n}={v}' for n, v in ui.items() if v)

    return render_template(
        'graph.html', uri=uri, label=label, column=column, inputs=inputs, ui=ui,
        show_filters=bool(ui['start'] or ui['stop']))


# USE a pure lambda ?
@app.route('/read/{label}/{column}')
def read(label, column):
    params = app.current_request.query_params or {}
    series = registry.get(label)
    start = params.pop("ui.start", None)
    stop = params.pop("ui.stop", None)

    # find time dimension
    tdim = None
    for name, coldef in series.schema.idx.items():
        if coldef.dt == 'datetime64[s]':
            tdim = name
            break
    else:
        # No time dimension found
        return

    # Query series
    page = int(params.get('ui.page', '0'))
    offset = page * PAGE_LEN
    extra_cols = tuple(col for col, value in params.items() if value)
    cols = (tdim, column) + extra_cols
    cur = series.select(*cols)
    frm = cur.limit(PAGE_LEN).offset(offset)[start:stop]

    # Slice other columns
    for col, value in params.items():
        if col not in frm.columns or not value:
            continue
        frm = frm.mask(frm[col] == int(value)) # FIXME

    # Aggregate on time dimension
    if len(series.schema.idx) > 1:
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
