#! /usr/bin/env python3

import argparse
import json
from pathlib import Path

from requests import Session
from conquer import sh


configs = {
    "dev": {
        "version": "2.0",
        "app_name": "lakota-lambda",
        "automatic_layer": True,
        "environment_variables": {
            "LAKOTA_URI": None,
            "APP_TITLE": "Lakota",
            "APP_PREFIX": "/api"
        },
        "stages": {
            "dev": {
                "api_gateway_stage": "api",
                "lambda_memory_size": 256,
                "minimum_compression_size": None
            }
        }
    },
    "local": {
        "version": "2.0",
        "app_name": "lakota-lambda",
        "environment_variables": {
            "LAKOTA_URI": None,
            "APP_TITLE": "Lakota"
        },
        "stages": {
            "dev": {
                "api_gateway_stage": "api"
            }
        }
    }
}

policy = '''{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": ["s3:GetObject"],
            "Resource": [
                "arn:aws:s3:::{bucket}/*"
            ],
            "Sid": "getbucket"
        },
        {
            "Effect": "Allow",
            "Action": [
            "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::{bucket}"
            ],
        "Sid": "listbucket"
        },              {
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            "Resource": "*",
            "Sid": "lambdalogs"
        }
    ]
}'''



libs = {
    'js': [
        'https://cdnjs.cloudflare.com/ajax/libs/jquery/3.5.1/jquery.min.js',
        'https://unpkg.com/htmx.org@0.0.8/dist/htmx.min.js',
        'https://cdnjs.cloudflare.com/ajax/libs/twitter-bootstrap/4.5.2/js/bootstrap.bundle.min.js',
        'https://leeoniya.github.io/uPlot/dist/uPlot.iife.min.js',
    ],
    'css': [
        'https://leeoniya.github.io/uPlot/dist/uPlot.min.css',
        'https://cdnjs.cloudflare.com/ajax/libs/twitter-bootstrap/4.5.2/css/bootstrap.min.css',
    ]
}


def config(cli):
    cfg = configs.get(cli.stage)
    if not cfg:
        print(f'Config not found for stage "{cli.stage}"')
        return
    if cli.kind == 'config':
        cfg['environment_variables']['LAKOTA_URI'] = cli.uri
    print(json.dumps(cfg, indent=4))


def policy(cli):
    # plc = policy.get(cli.stage)
    # if not cfg:
    #     print(f'Policy not found for stage "{cli.stage}"')
    #     return
    # Search for bucket in uri
    buckets = []
    for uri in cli.uri.split('+'):
        if not '://' in uri:
            continue
        protocol, path = uri.split("://", 1)
        if protocol != 's3':
            continue
        buckets.append(path)
    if not buckets:
        return

    # Format policy dict



def deploy(cli):
    stage = cli.stage
    if cli.stage not in ('local', 'dev'):
        exit('Nothing to do')

    # Copy config
    sh.cp(f'config-{stage}.json', '.chalice/config.json')

    # Build vendors libs
    static = Path('chalicelib/static')
    for ext in libs:
        vendor = static / f'vendor.{ext}'
        if vendor.exists():
            continue
        session = Session()
        with vendor.open('wb') as fh:
            for lib in libs[ext]:
                print(lib)
                resp = session.get(lib)
                resp.raise_for_status()
                fh.write(resp.content)
                fh.write(b'\n')

    # TODO policy

    # Run chalice
    if stage == 'local':
        res = sh.chalice.bg('local')
    elif stage == 'dev':
        res = sh.chalice.bg('deploy', '--no-autogen-policy')
    else:
        raise
    for line in res:
        print(line.strip())


def teardown(cli):
    for name in cli.bucket:
        print('Delete bucket', name)
        sh.aws('s3', 'rb', f's3://{name}', '--force')
    print('delete chalice app')
    sh.chalice('delete')


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")

    # CONFIG
    parser_config = subparsers.add_parser("config", help="Generate config files")
    parser_config.add_argument("stage", default='local',
                               help='Select stage')
    parser_config.add_argument(
        "--uri", "-u", help="Lakota URI"
    )
    parser_config.set_defaults(func=config)

    # DEPLOY
    parser_deploy = subparsers.add_parser("deploy", help='Deploy chalice app')
    parser_deploy.add_argument("stage", default='local',
                               help='Set up config and deploy the given stage (local or dev)')
    parser_deploy.set_defaults(func=deploy)

    # TEARDOWN
    parser_teardown = subparsers.add_parser("teardown", help="Delete lambda app and remove buckets")
    parser_teardown.add_argument(
        "--bucket", "-b", nargs="+", help="Bucket to delete"
    )
    parser_teardown.set_defaults(func=teardown)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return
    args.func(args)


if __name__ == '__main__':
    main()
