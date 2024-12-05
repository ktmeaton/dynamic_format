#!/usr/bin/env python3

import asyncio
from collections import OrderedDict
from datetime import datetime
import time
import psutil
import threading

import queue
import logging
from workflow import Workflow, QueuingHandler

from textual.app import App, ComposeResult
from textual.containers import Center, Middle, Horizontal
from textual import work, events
from textual.widgets import Header, Footer, Static, RichLog, Tree, Label, ProgressBar   


class TaskTree(Tree):
    BORDER_TITLE = "Tree"
    DEFAULT_CSS = """
    TaskTree {
        column-span: 2;
        height: 100%;
        border: solid yellow;
        border-title-align: center;
        padding: 1 1;
    }
    """
    pass

class Progress(Static):
    BORDER_TITLE = "Progress"
    DEFAULT_CSS = """
    Progress {
        column-span: 2;
        height: 100%;
        border: solid green;
        border-title-align: center;
        padding: 1 1;
    }
    """

    text = "Test"

    bars = OrderedDict()

    def compose(self) -> ComposeResult:
        #return self.add("default")
        yield Label(self.text)
        self.bars["default"] = ProgressBar()
        self.bars["extra"] = ProgressBar()
        self.bars["default"].total = 100
        for name,bar in self.bars.items():
            yield bar
    # def add(self, identifier) -> ComposeResult:
    #     # with Center():
    #     #     with Middle():
    #     #         self.bars[identifier] = ProgressBar()
    #     # yield self.bars[identifier]

class Resources(Static):
    BORDER_TITLE = "Resources"
    DEFAULT_CSS = """
    Resources {
        column-span: 1;
        height: 100%;
        border: solid blue;
        border-title-align: center;
        padding: 1 1;
    }
    """

    threads = threading.active_count()
    memory = psutil.virtual_memory().total >> 20
    fps = 0
    fps_time = datetime.now()

    def compose(self) -> ComposeResult:
        yield Label(f"Threads: {self.threads}")
        yield Label(f"Memory:  {self.memory} MB")
        yield Label(f"FPS:     {int(self.fps)}")

class Log(RichLog):
    BORDER_TITLE = "Log"
    DEFAULT_CSS = """
    Log {
        column-span: 5;
        height: 100%;
        border: solid red;
        border-title-align: center;
        padding: 1 1;
    }
    """

class Gui(App):
    AUTO_FOCUS = "Log"
    BINDINGS = [("d", "toggle_dark", "Toggle dark mode")]
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

    Horizontal#footer-outer {
        height: 1;
        dock: bottom;
    }
    Horizonal#footer-inner {
        width: 75%;
    }
    Label#right-label {
        width: 25%;
        text-align: right;
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
        yield Header()

        with Horizontal(id="footer-outer"):
            with Horizontal(id="footer-inner"):
                yield Footer()
            yield Label("This is the right side label", id="right-label")

        self.task_tree_lookup = {}
        self.task_tree = TaskTree("Tasks")
        self.task_tree.root.expand()
        yield self.task_tree
    
        self.progress = Progress()
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
        self.update_progress()
        self.update_resources()

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
                self.logger.debug(f"Add {job} progress bar")
                #self.progress.refresh(recompose)
                #self.progress.add(job)
                self.progress.refresh(recompose=True)
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

    @work
    async def update_resources(self):
        now = datetime.now()
        self.resources.fps = 1/ (now - self.resources.fps_time).total_seconds() 
        self.resources.fps_time = now
        self.resources.memory = psutil.virtual_memory().total >> 20
        self.resources.threads = threading.active_count()
        self.resources.refresh(recompose=True)

    @work
    async def update_progress(self):
        self.progress.text = "Updated"
        self.progress.bars["default"].advance(1)

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
    
