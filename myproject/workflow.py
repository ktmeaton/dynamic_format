#!/usr/bin/env/python3

import asyncio
import yaml
import time
from typing import List

import logging
import queue

class Step:
    def __init__(self, name, id):
        self.name = name
        self.id   = id

class TaskResult:
    def __init__(self, identifier):
        self.id  = identifier
    def __repr__(self):
        return f"{self.id}"

class Workflow:
    def __init__(self, path:str):
        """Create a Workflow based on a YAML path"""
        self.path = path

        with open(path) as infile:
            self.data = yaml.safe_load(infile)
        self.name = self.data["name"] if "name" in self.data else "unknown"
        self.jobs = self.data["jobs"] if "jobs" in self.data else {}
        

    async def run_job(self, job) -> List[asyncio.Task]:
        job_data = self.jobs[job]
        tasks = []
        if job_data == None or "steps" not in job_data and job_data["steps"] != None:
            return tasks
        else:
            for step,step_data in job_data["steps"].items():
                task = asyncio.create_task(self.demo(f"{job}.{step}"))
                tasks.append(task)
            return tasks


    async def demo(self, identifier):
        if step == "slow":
           time.sleep(5)

        return TaskResult(identifier)

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