#!/usr/bin/env/python3

import asyncio
from collections import OrderedDict
import yaml
import time
from typing import List

import argparse
import enum
import logging
import queue


class Display(enum.IntEnum):
    GUI = 1
    TEXT = 2

    def __str__(self):
        return self.name.lower()

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        try:
            return Display[s.upper()]
        except KeyError:
            return s

class Log():
    def __init__(
        self, 
        name:str       = "workflow",
        file:str       = "workflow.log",
        formatter:str  = '%(asctime)s %(name)-10s %(funcName)-14s %(levelname)-8s: %(message)s',
        level          = logging.INFO,
        datefmt        = '%Y-%m-%d %H:%M:%S',
        stdout         = True,
    ):
        self.name      = name
        self.file      = file
        self.formatter = formatter
        self.level     = level
        self.datefmt   = datefmt
        self.stdout    = stdout

class Workflow:
    def __init__(self, path:str, log:Log=None):
        """Create a Workflow based on a YAML path"""
        if log != None:
            self.log  = log
        else:
            self.log  = Log()
        self.logger   = None
        self.messages = queue.Queue()
        self.path     = path
        self.tasks    = OrderedDict()
        self.tree     = OrderedDict()

        self.create_logger()

        # with open(path) as infile:
        #     self.data = yaml.safe_load(infile)
        # self.name = self.data["name"] if "name" in self.data else "unknown"
        # self.jobs = self.data["jobs"] if "jobs" in self.data else {}
        # self.logger = logging.getLogger(name='workflow')

    # def __repr__(self):
    #     return 

    def create_logger(self) -> None:
        """Create a logger that sends messages to the queue."""
        #  Root logger
        logging.basicConfig(
            format=self.log.formatter,
            level=self.log.level,
            datefmt=self.log.datefmt,
            filename=self.log.file,
            filemode='w'
        )
        self.logger = logging.getLogger(name=self.log.name)
        formatter   = logging.Formatter(self.log.formatter, self.log.datefmt)
    
        # Add a handler to pass messages to our queue
        handler = QueuingHandler(message_queue=self.messages, level=self.log.level)
        handler.setFormatter(formatter)
        handler.setLevel(self.log.level)
        self.logger.addHandler(handler)

        # Add a handler to write messages to a file
        if self.log.file:
            file_handler = logging.FileHandler(self.log.file)
            file_handler.setFormatter(formatter)
            file_handler.setLevel(self.log.level)
            self.logger.addHandler(file_handler)

        # Add a handler to write messages to stdout
        if self.log.stdout:
            stdout_handler = logging.StreamHandler()
            stdout_handler.setFormatter(formatter)
            stdout_handler.setLevel(self.log.level)
            self.logger.addHandler(stdout_handler)
    
        self.logger.debug(f"Logger ready.")

    async def load(self) -> None:
        self.logger.info(f"Loading workflow: {self.workflow_yaml}")
        self.workflow = Workflow(self.workflow_yaml)
        self.logger.info(f"Workflow loaded: {self.workflow.name}")
        self.title = self.workflow.name

    def run_workflow(self, log_name: str):
        """Run workflow and add tasks to the queue."""
        logger = logging.getLogger(name=log_name)
        self.logger.info("Running workflow.")
        for job,job_data in self.jobs.items():
            self.validate_job(job, logger)
            self.tree[job] = OrderedDict()
            # steps = job_data["steps"] if "steps" in job_data and job_data["steps"] != None else {}
            # for step,step_data in job_data["steps"].items():
            #     logger.info(f"Running step: {step}")
            #     if step in self.tree[job]:
            #         msg = "Step name {step} is not unique to job {job}."
            #         logger.error(msg)
            #         raise Exception(msg)
            #     for i,task in enumerate(step_data):
            #         identifier = f"{job}.{step}.{task}.{i}"
            #         if task in self.tree[job][step]:
            #             msg = "Task name {task} is not unique to step {step}."
            #             logger.error(msg)
            #             raise Exception(msg)
            #         logger.info(f"Dispatching task: {identifier}")
            #         t = asyncio.create_task(self.demo(identifier))
            #         self.tasks[identifier] = t

    def validate_job(self, job, logger):
        logger.info(f"Validating job: {job}")
        if job in self.tree:
            msg = "Job name '{job}' is not unique."
            logger.error(msg)
            raise Exception(msg)

    def get_steps(self, job) -> dict:
        d = self.jobs[job]
        return d["steps"] if "steps" in d and d["steps"] != None else {}

    def get_tasks(self, job, step) -> dict:
        return self.jobs[job]["steps"][step]

    async def demo(self, identifier):
        if "slow" in identifier:
           time.sleep(5)
        return identifier

class QueuingHandler(logging.Handler):
    """
    Author: user2676699
    Source: https://stackoverflow.com/a/36411214
    A thread safe logging.Handler that writes messages into a queue object.

    Designed to work with LoggingWidget so log messages from multiple
    threads can be shown together in a single ttk.Frame.

    The standard logging.QueueHandler/logging.QueueListener can not be used
    for this because the QueueListener runs in a private thread, not the
    main thread.

    Warning:  If multiple threads are writing into this Handler, all threads
    must be joined before calling logging.shutdown() or any other log
    destinations will be corrupted.
    """

    def __init__(self, *args, message_queue, **kwargs):
        """Initialize by copying the queue and sending everything else to superclass."""
        logging.Handler.__init__(self, *args, **kwargs)
        self.message_queue = message_queue

    def emit(self, record):
        """Add the formatted log message (sans newlines) to the queue."""
        self.message_queue.put(self.format(record).rstrip('\n'))