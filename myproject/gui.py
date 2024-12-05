#!/usr/bin/env python3

import asyncio
from datetime import datetime
import time

import queue
import logging
from workflow import Workflow, QueuingHandler

from textual.app import App, ComposeResult
from textual import work, events
from textual.widgets import Header, Footer, Static, RichLog, Tree

class TaskTree(Tree):
    DEFAULT_CSS = """
    TaskTree {
        column-span: 2;
        height: 100%;
        border: solid yellow;
    }
    """
    pass

class Progress(Static):
    DEFAULT_CSS = """
    Progress {
        column-span: 2;
        height: 100%;
        border: solid green;
    }
    """

class Resources(Static):
    DEFAULT_CSS = """
    Resources {
        column-span: 1;
        height: 100%;
        border: solid blue;
    }
    """

class Log(RichLog):
    DEFAULT_CSS = """
    Log {
        column-span: 5;
        height: 100%;
        border: solid red;
    }
    """

class Gui(App):
    CSS = """
    Screen {
        layout: grid;
        grid-size: 5;
        grid-rows: 60% 40%;
    }

    .resources {
        column-span: 1;
        height: 100%;
        border: solid yellow;
    }

    .log {
        column-span: 5;
        height: 100%;
        border: solid yellow;
    }
    """

    message_queue = queue.Queue()
    workflow = None

    def __init__(self, fps:int=60, workflow_yaml:dict={}, safe:bool=True, log:str="myproject.log"):
        self.fps = fps
        self.workflow_yaml = workflow_yaml
        self.logfile = log
        super().__init__()

    def compose(self) -> ComposeResult:
        self.header = Header()
        yield self.header
        self.footer = Footer()
        yield self.footer

        self.task_tree = TaskTree("Tasks")
        yield self.task_tree
    
        self.progress = Progress("Progress")
        yield self.progress
    
        self.resources = Resources("Resources")
        yield self.resources

        self.run_log = Log(highlight=True, markup=True)
        yield self.run_log

    async def on_mount(self) -> None:
        self.title = "Title"
        self.subtitle = "subtitle"

        self.create_logger()
        self.logger.info("GUI loaded.")

        self.gui = self.set_interval(1 / self.fps, self.update_gui)
        self.gui.resume()
        # self.load_workflow()
        # self.run_workflow()


    def create_logger(self) -> None:
        LOG_FORMAT = '%(asctime)s %(name)6s %(levelname)8s: %(message)s'
        #  Setup root logger to write to a log file.
        logging.basicConfig(
            format=LOG_FORMAT,
            level=logging.DEBUG,
            datefmt='%Y-%m-%d %H:%M:%S',
            filename=self.logfile,
            filemode='w'
        )

        #  Get a child logger
        self.logger = logging.getLogger(name='gui')

        #  Build our QueuingHandler
        handler = QueuingHandler(message_queue=self.message_queue, level=logging.DEBUG)

        #  Change the date/time format for the GUI to drop the date
        formatter = logging.Formatter(LOG_FORMAT)
        formatter.default_time_format = '%H:%M:%S'
        handler.setFormatter(formatter)

        #  Add our QueuingHandler into the logging heirarchy at the lower level
        self.logger.addHandler(handler)
        self.logger.info("INFO in gui")
        self.logger.debug("DEBUG in gui")

    @work
    async def update_gui(self) -> None:
        # Update log
        message = self.message_queue.get()
        #message_queue, self.message_queue = list(self.message_queue), queue.Queue()
        # for message in message_queue:
        #     now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        #     self.run_log.write(f"{now} [INFO] {message}")


    def load_workflow(self) -> None:
        #self.message_queue.append(f"Loading workflow: {self.workflow_yaml}")
        self.workflow = Workflow(self.workflow_yaml)
        #self.messages.append(f"Workflow loaded: {self.workflow.name}")
        self.title = self.workflow.name
        #self.messages.append(self.workflow.jobs)
        #self.task_tree.root.add("test")
        #self.task_tree.add_json(self.workflow.jobs)


    @work(thread=True)
    async def run_workflow(self) -> None:
        self.messages.append(f"Beginning workflow.")
        tasks = []
        for job in self.workflow.jobs:
            self.messages.append(f"Starting job: {job}")
            tasks = await self.workflow.run_job(job)
            for task in asyncio.as_completed(tasks):
                result = await task
                self.messages.append(f"task: {result}")
            #     #await task
            # # #     self.messages.append(messages)
        self.messages.append(f"Completed workflow.")


    def on_key(self, event: events.Key) -> None:
        self.logger.debug(event)
        #self.messages.append(event)
    
