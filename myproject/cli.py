import logging
import os
import sys
from workflow import QueuingHandler
import queue

#LOGLEVEL = os.environ["LOGLEVEL"] if "LOGLEVEL" in os.environ else "INFO"
#logging.basicConfig(level=LOGLEVEL.upper(), format='%(asctime)s %(levelname)s:%(message)s')

def get_options():
    import argparse

    description = 'Description goes here!.'
    parser = argparse.ArgumentParser(description=description)

    #parser.add_argument('--display', help=f"Display mode. (default: {Display.RICH})", type=Display.argparse, choices=list(Display), default=Display.RICH)
    parser.add_argument('-w', '--workflow', dest="workflow_yaml", help="Workflow YAML file", required=True)
    parser.add_argument('--unsafe', help="Enabled unsafe mode", dest="safe", action="store_false")
    parser.add_argument('--fps', help="GUI refresh rate. (default: 60)", type=int, default=60)
    parser.add_argument('--log', help="Path to log file. (default: myproject.log", type=str, default="myproject.log")
    return parser.parse_args()

from gui import Gui

if __name__ == "__main__":

    options = get_options()
    kwargs = vars(options)

    # LOG_FORMAT = '%(asctime)s %(name)6s %(levelname)8s: %(message)s'
    # #  Setup root logger to write to a log file.
    # logging.basicConfig(
    #     format=LOG_FORMAT,
    #     level=logging.DEBUG,
    #     datefmt='%Y-%m-%d %H:%M:%S',
    #     filename=options.log,
    #     filemode='w'
    # )

    # #  Get a child logger
    # logger = logging.getLogger(name='gui')

    # #  Build our QueuingHandler
    # message_queue = queue.Queue()
    # handler = QueuingHandler(message_queue=message_queue, level=logging.DEBUG)

    # #  Change the date/time format for the GUI to drop the date
    # formatter = logging.Formatter(LOG_FORMAT)
    # formatter.default_time_format = '%H:%M:%S'
    # handler.setFormatter(formatter)

    # #  Add our QueuingHandler into the logging heirarchy at the lower level
    # logger.addHandler(handler)
    # logger.info("INFO")
    # logger.debug("DEBUG")

    # print(message_queue.get())

    # # set up logging to file - see previous section for more details
    # logging.basicConfig(level=logging.DEBUG,
    #                     format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
    #                     datefmt='%m-%d %H:%M',
    #                     filename=options.log,
    #                     filemode='w')
                    
    # # define a Handler which writes INFO messages or higher to the sys.stderr
    # console = logging.StreamHandler()
    # console.setLevel(logging.INFO)
    # # set a format which is simpler for console use
    # formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
    # # tell the handler to use this format
    # console.setFormatter(formatter)
    # # add the handler to the root logger
    # logging.getLogger('').addHandler(console)

    # # Now, we can log to the root logger, or any other logger. First the root...
    # logging.info('Jackdaws love my big sphinx of quartz.')

    # # Now, define a couple of other loggers which might represent areas in your
    # # application:

    # logger1 = logging.getLogger('myapp.area1')
    # logger2 = logging.getLogger('myapp.area2')

    # logger1.debug('Quick zephyrs blow, vexing daft Jim.')
    # logger1.info('How quickly daft jumping zebras vex.')
    # logger2.warning('Jail zesty vixen who grabbed pay from quack.')
    # logger2.error('The five boxing wizards jump quickly.')

    gui = Gui(**kwargs)
    gui.run()