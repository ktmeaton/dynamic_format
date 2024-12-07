#!/usr/bin/env python3

import asyncio
from collections import OrderedDict
from datetime import datetime
import time
import psutil
import threading

import queue
import logging
from workflow import Workflow, QueuingHandler, Log

from textual.app import App, ComposeResult
from textual.containers import HorizontalGroup, Horizontal, Center, Middle
from textual import work, events
from textual.widgets import Header, Footer, Static, RichLog, Tree, Label, ProgressBar
from textual.timer import Timer  
from textual.renderables import bar


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

class ProgressJob(HorizontalGroup):
    DEFAULT_CSS = """
    Label {
        width: 14;
    }
    .custom-bar Bar {
        width: 15;
    }
    .custom-bar Bar > .bar--bar {
        color: blue;
        background: yellow 30%;
    }
    """
    job = None
    total = 0
    steps = 0
    label = None
    bar = None
    max_label_len = 10

    def __init__(self, job:str, total:int=0, completed:int=0):
        self.job = job
        self.total = total
        super().__init__()

    def compose(self) -> ComposeResult:
        if len(self.job) > self.max_label_len:
            self.label = Label(f"{self.job[0:self.max_label_len]}...")
        else:
            self.label = Label(self.job)
        yield self.label
        self.bar = ProgressBar(10, classes="custom-bar")
        self.bar.advance(5)
        yield self.bar

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

    jobs = OrderedDict()

    def add_job(self, job:str, total=None) -> None:
        self.jobs[job] = ProgressJob(job=job, total=total)
        self.mount(self.jobs[job])

class Backend(Static):
    BORDER_TITLE = "Backend"
    DEFAULT_CSS = """
    Backend {
        column-span: 1;
        height: 100%;
        border: solid blue;
        border-title-align: center;
        padding: 1 1;
    }
    """

    threads = threading.active_count()
    memory = psutil.virtual_memory().used >> 20
    fps = 0
    fps_time = datetime.now()
    concurrent = 0
    messages = 0
    tasks = 0

    def compose(self) -> ComposeResult:
        yield Label(f"Threads:     {self.threads}")
        yield Label(f"Memory:      {self.memory} MB")
        yield Label(f"FPS:         {int(self.fps)}")
        yield Label(f"Concurrent:  {self.concurrent}")
        yield Label(f"Messages:    {self.messages}")
        yield Label(f"Tasks:       {self.tasks}")

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

    .backend {
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
    messages = queue.Queue()
    workflow = None

    def __init__(self, path:str, fps:int=60, safe:bool=True, log:Log=None):
        self.fps = fps
        self.workflow = Workflow(path, log=log)
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
    
        self.backend = Backend()
        yield self.backend

        self.run_log = Log(highlight=True, markup=True)
        yield self.run_log

    async def on_mount(self) -> None:
        self.title = "Title"
        self.subtitle = "subtitle"

        self.create_logger()
        self.logger.info("This is an info test.")
        self.logger.warning("This is a warning test.")
        #self.load_workflow()
        # Create a logger and connect it to the message queue
        # self.create_logger()

        # Start a GUI-updating function that runs at FPS
        self.gui = self.set_interval(1 / self.fps, self.update_gui)
        self.gui.resume()

        # # Display resource usage at a slower FPS (2), otherwise it's distracting
        # # how fast the numbers change.
        # self.backend_updater = self.set_interval(1 / 2, self.update_backend)
        # self.backend_updater.resume()

        # Load the workflow YAML 
        #await self.load_workflow()

        # Start running the workflow
        # self.run_workflow()


    def create_logger(self) -> None:
        """Create a logger that sends messages to the queue."""
        self.logger = logging.getLogger(name="gui")
        handler     = QueuingHandler(message_queue=self.messages, level=self.workflow.log.level)
        formatter   = logging.Formatter(self.workflow.log.formatter)

        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.debug(f"Logger ready.")

    @work
    async def update_gui(self) -> None:
        self.update_log()
        #self.update_tree()
        #self.update_progress()
        #self.calculate_resources()


    @work
    async def update_log(self):
        if not self.messages.empty():
            message = self.messages.get()
            self.run_log.write(message)
        if not self.workflow.messages.empty():
            message = self.workflow.messages.get()
            self.run_log.write(message)
    @work
    async def update_tree(self):
        for job in self.workflow.jobs:
            identifier = job
            if job not in self.task_tree_lookup:
                job_node = self.task_tree.root.add(job, expand=True)
                self.task_tree_lookup[identifier] = job_node
                self.logger.debug(f"Adding progress bar: {job}")
                self.progress.add_job(job)
                #self.progress.refresh(recompose)

                #self.progress.mount(Label(job))
                #self.progress.mount(ProgressBar())
                #self.progress.refresh(recompose=True)
            # else:
            #     job_node = self.task_tree_lookup[job]
            # for step in self.workflow.get_steps(job):
            #     identifier = f"{job}.{step}"
            #     if identifier not in self.task_tree_lookup:
            #         step_node = job_node.add(step, expand=True)
            #         self.task_tree_lookup[identifier] = step_node 
            #     else:
            #         step_node = self.task_tree_lookup[identifier]
            #     for task in self.workflow.get_tasks(job, step):
            #         identifier = f"{job}.{step}.{task}"
            #         if identifier not in self.task_tree_lookup: 
            #             task_label = "{:10} {:5}".format(task, "⏩")
            #             task_node = step_node.add_leaf(task_label)
            #             self.task_tree_lookup[identifier] = task_node 
            #         else:
            #             task_node = self.task_tree_lookup[identifier]

    @work
    async def calculate_resources(self):
        now = datetime.now()
        self.backend.fps = 1/ (now - self.backend.fps_time).total_seconds() 
        self.backend.fps_time = now
        self.backend.memory = psutil.virtual_memory().used >> 20
        self.backend.threads = threading.active_count()
        self.backend.concurrent = len(asyncio.all_tasks())
        self.backend.messages = self.messages.qsize()
        self.backend.tasks = len(self.workflow.tasks)

    @work
    async def update_backend(self):
        self.backend.refresh(recompose=True)

    @work
    async def update_progress(self):
        pass
        #self.progress.text = "Updated"
        #self.progress.bars["default"].advance(1)

    async def load_workflow(self) -> None:
        self.workflow = Workflow(self.path)
        #self.title = self.workflow.name
        # self.logger.info(f"Loading workflow: {self.path}")
        # self.workflow = Workflow(self.path)
        # self.logger.info(f"Workflow loaded: {self.workflow.name}")


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
    
