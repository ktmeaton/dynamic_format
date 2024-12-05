#!/usr/bin/env python3

import asyncio
from datetime import datetime
import time

import queue
import logging
from workflow import Workflow, QueuingHandler

from textual.app import App, ComposeResult
from textual import work, events
from textual.widgets import Header, Footer, Static, RichLog, Tree, Label
from textual.widgets.tree import UnknownNodeID


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
        border-title-align: center;
        padding: 1 1;
    }
    """
    BORDER_TITLE = "Resources"

    def compose(self) -> ComposeResult:
        yield Label("Threads:")
        yield Label("Memory:")

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

        self.task_tree_lookup = {}
        self.task_tree = TaskTree("Tasks")
        self.task_tree.root.expand()
        yield self.task_tree
    
        self.progress = Progress("Progress")
        yield self.progress
    
        self.resources = Resources()
        yield self.resources

        self.run_log = Log(highlight=True, markup=True)
        yield self.run_log

    async def on_mount(self) -> None:
        self.title = "Title"
        self.subtitle = "subtitle"

        self.create_logger()
        self.gui = self.set_interval(1 / self.fps, self.update_gui)
        self.gui.resume()

        await self.load_workflow()
        self.run_workflow()


    def create_logger(self) -> None:
        #log_format = '%(asctime)s %(name)6s %(levelname)8s: %(message)s'
        log_format = '%(asctime)s %(funcName)20s %(levelname)8s: %(message)s'
        #  Root logger
        logging.basicConfig(
            format=log_format,
            level=logging.DEBUG,
            datefmt='%Y-%m-%d %H:%M:%S',
            filename=self.logfile,
            filemode='w'
        )
        # Child logger
        self.logger = logging.getLogger(name="gui")
        handler = QueuingHandler(message_queue=self.message_queue, level=logging.DEBUG)
        formatter = logging.Formatter(log_format)
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.debug("Logger ready.")

    @work
    async def update_gui(self) -> None:
        self.update_log()
        self.update_tree()
        # TODO: self.update_progress()
        # TODO: self.update_resources()

    @work
    async def update_log(self):
        if not self.message_queue.empty():
            message = self.message_queue.get()
            self.run_log.write(message)

    @work
    async def update_tree(self):
        for job in self.workflow.jobs:
            identifier = job
            if job not in self.task_tree_lookup:
                job_node = self.task_tree.root.add(job, expand=True)
                self.task_tree_lookup[identifier] = job_node
            else:
                job_node = self.task_tree_lookup[job]
            for step in self.workflow.get_steps(job):
                identifier = f"{job}.{step}"
                if identifier not in self.task_tree_lookup:
                    step_node = job_node.add(step, expand=True)
                    self.task_tree_lookup[identifier] = step_node 
                else:
                    step_node = self.task_tree_lookup[identifier]
                for task in self.workflow.get_tasks(job, step):
                    identifier = f"{job}.{step}.{task}"
                    if identifier not in self.task_tree_lookup: 
                        task_label = "{:10} {:5}".format(task, "⏩")
                        task_node = step_node.add_leaf(task_label)
                        self.task_tree_lookup[identifier] = task_node 
                    else:
                        task_node = self.task_tree_lookup[identifier]

    async def load_workflow(self) -> None:
        self.logger.info(f"Loading workflow: {self.workflow_yaml}")
        self.workflow = Workflow(self.workflow_yaml)
        self.logger.info(f"Workflow loaded: {self.workflow.name}")
        self.title = self.workflow.name


    @work(thread=True)
    async def run_workflow(self) -> None:
        tasks = self.workflow.run_workflow(log_name='gui')
        # for task in asyncio.as_completed(self.workflow.task_queue):
        #     self.logger.info(f"Waiting for task: {task}")
        #     result = await task
        #     self.logger.info(f"Completed task: {result}")
        #for task in asyncio.as_completed(tasks): 
        #   result = await task
        #self.logger.info("Workflow complete.")
        # self.messages.append(f"Beginning workflow.")
        # tasks = []
        # for job in self.workflow.jobs:
        #     self.messages.append(f"Starting job: {job}")
        #     tasks = await self.workflow.run_job(job)
        #     for task in asyncio.as_completed(tasks):
        #         result = await task
        #         self.messages.append(f"task: {result}")
        #     #     #await task
        #     # # #     self.messages.append(messages)


    def on_key(self, event: events.Key) -> None:
        self.logger.debug(event)
    
