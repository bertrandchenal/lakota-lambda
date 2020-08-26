#! /usr/bin/env python3

import argparse
import json

from conquer import sh


configs = {
    "dev": {
        "version": "2.0",
        "app_name": "jensen-lambda",
        "automatic_layer": True,
        "environment_variables": {
            "DB_BUCKET": None,
            "APP_TITLE": "Jensen",
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
        "app_name": "jensen-lambda",
        "environment_variables": {
            "DB_BUCKET": None,
            "APP_TITLE": "Jensen"
        },
        "stages": {
            "dev": {
                "api_gateway_stage": "api"
            }
        }
    }


}

def config(cli):
    cfg = configs.get(cli.stage)
    if not cfg:
        print(f'Config not found for stage "{cli.stage}"')
        return
    cfg['environment_variables']['DB_BUCKET'] = cli.bucket
    print(json.dumps(cfg, indent=4))


def deploy(cli):
    stage = cli.stage
    if cli.stage not in ('local', 'dev'):
        exit('Nothing to do')

    # Copy config
    sh.cp(f'config-{stage}.json', '.chalice/config.json')

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

    parser_config = subparsers.add_parser("config", help="Config config files")
    parser_config.add_argument("stage", default='local',
                               help='Select stage')
    parser_config.add_argument(
        "--bucket", "-b", help="Bucket holding Jensen DB"
    )
    parser_config.set_defaults(func=config)

    parser_deploy = subparsers.add_parser("deploy", help='Deploy chalice app')
    parser_deploy.add_argument("stage", default='local',
                               help='Set up config and deploy the given stage (local or dev)')
    parser_deploy.set_defaults(func=deploy)

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
