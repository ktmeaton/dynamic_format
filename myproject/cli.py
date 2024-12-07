import logging
import os
import sys
from workflow import QueuingHandler, Log, Display, Workflow
import queue
import enum
import copy

#LOGLEVEL = os.environ["LOGLEVEL"] if "LOGLEVEL" in os.environ else "INFO"
#logging.basicConfig(level=LOGLEVEL.upper(), format='%(asctime)s %(levelname)s:%(message)s')

def get_options(args:str=None):
    """
    Parse CLI options.

    Returns a tuple of the original arguments, and the parsed arguments.

    >>> sys.argv, options = get_options("myproject -p workflow.yaml")

    """
    import argparse

    sys_argv_original = sys.argv
    if args != None:
        sys.argv = args.split(" ")

    description = 'Description goes here!.'
    parser = argparse.ArgumentParser(description=description)

    parser.add_argument('-d', '--display', type=Display.argparse, choices=list(Display), default=Display.GUI)
    parser.add_argument('-p', '--path', help="Workflow YAML file", required=True)

    parser.add_argument('--unsafe',     help="Enabled unsafe mode", dest="safe", action="store_false")
    parser.add_argument('--fps',        help="GUI refresh rate. (default: 60)", type=int, default=60)
    parser.add_argument('--log',        help="Path to log file. (default: myproject.log)", type=str, dest="log", default="myproject.log")
    
    return (sys_argv_original, parser.parse_args())

from gui import Gui

if __name__ == "__main__":

    # Parse CLI options
    sys_argv_original = sys.argv
    sys.argv, options = get_options("test -p path --display text")

    # Adjust the default log level based on environment variables
    log_level = os.environ["LOGLEVEL"].upper() if "LOGLEVEL" in os.environ else "INFO"

    # Log configuration that will be used by all display options.
    log = Log(level=log_level, file=options.log)
    workflow = Workflow(path=options.path, log=log) 
    workflow.logger.debug("This is a debug test.")
    workflow.logger.info("This is an info test.")
    workflow.logger.warning("This is a warning test.")

    # # Display/run Option 1.
    # if options.display == Display.GUI:
    #     log.stdout = False
    #     kwargs = {k:v for k,v in vars(options).items() if k in ["path", "safe", "fps"]}
    #     kwargs["log"] = log
    #     Gui(**kwargs).run()
    # elif options.display == Display.TEXT:
    #     log.stdout = True
    #     workflow = Workflow(path=options.path, log=log) 
    #     workflow.logger.debug("This is a debug test.")
    #     workflow.logger.info("This is an info test.")
    #     workflow.logger.warning("This is a warning test.")
