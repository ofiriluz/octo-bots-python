import argparse
import os
import sys

import yaml
from flask import Flask

from octo_bots_python.bots_flask_manager import BotsFlaskManager
from octo_bots_python.common.logger import Logger

logger = Logger("bots_executor")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-cp", "--config-path", help="Path to YAML config for the bots", required=True)
    args = parser.parse_args()

    if not os.path.exists(args.config_path):
        logger.error("Invalid config path, aborting")
        sys.exit(1)

    flask_app = Flask(__name__)

    bots_manager = BotsFlaskManager.create_bots_manager(args.config_path, flask_app)

    bots_manager.start_bots_manager()

    flask_app.run(ssl_context="adhoc", host="0.0.0.0", port=8443, debug=False)


if __name__ == "__main__":
    main()
