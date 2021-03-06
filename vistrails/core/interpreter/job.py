###############################################################################
##
## Copyright (C) 2011-2013, NYU-Poly.
## Copyright (C) 2006-2011, University of Utah. 
## All rights reserved.
## Contact: contact@vistrails.org
##
## This file is part of VisTrails.
##
## "Redistribution and use in source and binary forms, with or without 
## modification, are permitted provided that the following conditions are met:
##
##  - Redistributions of source code must retain the above copyright notice, 
##    this list of conditions and the following disclaimer.
##  - Redistributions in binary form must reproduce the above copyright 
##    notice, this list of conditions and the following disclaimer in the 
##    documentation and/or other materials provided with the distribution.
##  - Neither the name of the University of Utah nor the names of its 
##    contributors may be used to endorse or promote products derived from 
##    this software without specific prior written permission.
##
## THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" 
## AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, 
## THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR 
## PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR 
## CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, 
## EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, 
## PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; 
## OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, 
## WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR 
## OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF 
## ADVISED OF THE POSSIBILITY OF SUCH DAMAGE."
##
###############################################################################
""" Contains classes for persisting running executions to disk
    
"""

from vistrails.core.configuration import get_vistrails_configuration
from vistrails.core.system import current_dot_vistrails
from vistrails.core.modules.module_registry import get_module_registry
from vistrails.core.modules.vistrails_module import ModuleSuspended, NotCacheable

from uuid import uuid1

import datetime
import getpass
import json
import os
import time
import unittest
import weakref

JOBS_FILENAME = "jobs.json"

class JobMixin(NotCacheable):
    """ Provides a finished compute method for implementing job handling
        The package developer needs to implement the method stubs

    """
    
    def compute(self):
        params = self.readInputs()
        signature = self.getId(params)
        jm = JobMonitor.getInstance()
        # use cached job if it exist
        cache = jm.getCache(signature)
        if cache:
            self.setResults(cache.parameters)
            return
        # check if job is running
        job = jm.getJob(signature)
        if job:
            params = job.parameters
        else:
            # start job
            params = self.startJob(params)
            # set visible name
            # check custom name
            m = self.interpreter._persistent_pipeline.modules[self.id]
            if '__desc__' in m.db_annotations_key_index:
                name = m.get_annotation_by_key('__desc__').value.strip()
            else:
                reg = get_module_registry()
                name = reg.get_descriptor(self.__class__).name
            jm.addJob(signature, params, name)
        # call method to check job
        jm.checkJob(self, signature, self.getMonitor(params))
        # job is finished, set outputs
        params = self.finishJob(params)
        self.setResults(params)
        cache = jm.setCache(signature, params)
        
    def readInputs(self):
        """readInputs() -> None
            Should read inputs, and return them in a dict
        
        """
        raise NotImplementedError

    def startJob(self, params):
        """startJob(params: dict) -> None
            Should start the job, and return a dict with the 
            parameters needed to check the job
        
        """
        raise NotImplementedError

    def finishJob(self, params):
        """finishJob(params: dict) -> None
            Should finish the job and set outputs
            
        """
        raise NotImplementedError
        
    def setResults(self, params):
        """ setResults(params: dict) -> None
            Sets outputs using the params dict
        """
        raise NotImplementedError

    def getMonitor(self, params):
        """ getMonitor(params: dict) -> None
            Should return an instance with methods for checking the job state
            Possible methods
            .finished() - required, returns True if job has completed
        """
        return None

    def getId(self, params):
        """ getId(params: dict) -> job identifier
            Should return an string completely identifying this job
            Class name + input values are usually unique
            WARNING: The default implementation does not work correctly in
                     maps and groups
        """
        return self.signature
    
class Workflow:
    """ Represents a running workflow
        Modules can register their state
        It can be serialized to disk

    """
    def __init__(self, vistrail, version, name='untitled', id=None, user=None,
                 start=None, modules=[]):
        """ __init__(vistrail: str, version: str/int, name: str, id: str,
            user: str, start: str, modules: list) -> None

            vistrail - the vistrail url
            version - workflow version
            name - a human readable name for the job
            id - persistent identifier
            user - who started the job
            start - start time
            finished - is it finished or running?
        
        """
        self.vistrail = vistrail
        self.version = version
        self.name = name
        self.id = id if id else str(uuid1())
        self.user = getpass.getuser()
        self.start = start if start else str(datetime.datetime.now())
        self.modules = modules if modules else {}
        # parent modules are stored as temporary exceptions
        self.parents = {}

    def to_dict(self):
        wf = dict()
        wf['vistrail'] = self.vistrail
        wf['version'] = self.version
        wf['id'] = self.id
        wf['name'] = self.name
        wf['user'] = self.user
        wf['start'] = self.start
        modules = dict()
        for module in self.modules.itervalues():
            modules[module.id] = module.to_dict()
        wf['modules'] = modules
        return wf

    @staticmethod
    def from_dict(wf):
        modules = {}
        for id, module in wf['modules'].iteritems():
            modules[id] = Module.from_dict(module)
        return Workflow(wf['vistrail'], wf['version'], wf['name'], wf['id'],
                        wf['user'], wf['start'], modules)

    def __eq__(self, other):
        if self.vistrail != other.vistrail: return False
        if self.version != other.version: return False
        if self.name != other.name: return False
        if self.id != other.id: return False
        if self.user != other.user: return False
        if self.start != other.start: return False
        if len(self.modules) != len(other.modules): return False
        if self.modules != other.modules: return False
        return True

    def reset(self):
        for job in self.modules.itervalues():
            job.reset()
        self.parents = {}

    def completed(self):
        """ Returns true if there are no suspended jobs
        """
        for job in self.modules.itervalues():
            if not job.finished:
                return False
        return True
        
        
class Module:
    """ Represents a running module
        
    """
    def __init__(self, id, parameters, name='', start=None, finished=False):
        """ __init__(id: str, parameters: dict, name: str, start: str,
                     finished: bool)

            id - persistent identifier
            parameters - either output values or job parameters
            start - start time
            finished - is it finished or running?
        
        """
        self.id = id
        self.parameters = parameters
        self.name = name
        self.start = start if start else str(datetime.datetime.now())
        self.finished = finished
        self.updated = True

    def reset(self):
        self.updated = False

    def mark(self):
        self.updated = True

    def finish(self, params=None):
        self.params = params if params else {}
        self.finished = True
    
    def description(self):
        return self.parameters.get('__desc__', '')

    def to_dict(self):
        m = dict()
        m['id'] = self.id
        m['parameters'] = self.parameters
        m['name'] = self.name
        m['start'] = self.start
        m['finished'] = self.finished
        return m

    @staticmethod
    def from_dict(m):
        return Module(m['id'], m['parameters'], m['name'], m['start'], m['finished'])

    def __eq__(self, other):
        if self.id != other.id: return False
        if self.parameters != other.parameters: return False
        if self.start != other.start: return False
        if self.finished != other.finished: return False
        return True
        
class JobMonitor:
    """ A singleton class keeping a list of running jobs and the current job

    """

    #Singleton technique
    _instance = None
    class JobMonitorSingleton():
        def __call__(self, *args, **kw):
            if JobMonitor._instance is None:
                obj = JobMonitor(*args, **kw)
                JobMonitor._instance = obj
            return JobMonitor._instance
    getInstance = JobMonitorSingleton()
    
    def __init__(self, filename=None):
        self._current_workflow = None
        self._running_workflows = {}
        self.callback = None
        self.load_from_file(filename)

    def setCallback(self, callback=None):
        """ setCallback(callback: class) -> None
            Sets a callback when receiving commands

        """
        self.callback = weakref.proxy(callback)

##############################################################################
# Running Workflow

    def __serialize__(self):
        """ __serialize__() -> None
            serializes the running jobs to json

        """ 
        jobs = dict()
        for id, workflow in self._running_workflows.items():
            jobs[id] = workflow.to_dict()
        return json.dumps(jobs)
    
    def __unserialize__(self, s):
        """ __unserialize__(s: str) -> None
            unserializes the running jobs from json

        """ 
        jobs = json.loads(s)
        self._running_workflows = {}
        for id, workflow in jobs.iteritems():
            self._running_workflows[id] = Workflow.from_dict(workflow)
        return self._running_workflows
    
    def save_to_file(self, filename=None):
        """ save_to_file(filename: str) -> None
            Saves running jobs to a file

        """ 
        if not filename:
            filename = os.path.join(current_dot_vistrails(), JOBS_FILENAME)
        f = open(filename, 'w')
        f.write(self.__serialize__())
        f.close()

    def load_from_file(self, filename=None):
        """ load_from_file(filename: str) -> None
            Loads running jobs from a file
            
        """
        if not filename:
            filename = os.path.join(current_dot_vistrails(), JOBS_FILENAME)
        if not os.path.exists(filename):
            self.__unserialize__('{}')
            return {}
        f = open(filename)
        result =  self.__unserialize__(f.read())
        f.close()
        return result

    def getWorkflow(self, id):
        """ getWorkflow(id: str) -> Workflow
        
            Checks if a workflow exists using its id and returns it

        """
        return self._running_workflows.get(id, None)

    def deleteWorkflow(self, id):
        """ deleteWorkflow(id: str) -> None
            deletes a workflow

        """
        del self._running_workflows[id]
        if self.callback:
            self.callback.deleteWorkflow(id)

    def deleteJob(self, id, parent_id=None):
        """ deleteJob(id: str, parent_id: str) -> None
            deletes a job
            if parent_id is None, the current workflow is used
        """
        if not parent_id:
            if not self._current_workflow:
                raise Exception("No workflow is running!")
                return
            parent_id = self._current_workflow.id
        del self._running_workflows[parent_id].modules[id]
        if self.callback:
            self.callback.deleteJob(id, parent_id)

##############################################################################
# _current_workflow methods
    
    def currentWorkflow(self):
        """ currentWorkflow() -> Workflow
        
        """
        return self._current_workflow

    def startWorkflow(self, workflow):
        """ startWorkflow(workflow: Workflow) -> None
        
        """
        if self._current_workflow:
            raise Exception("A workflow is still running!: %s" %
                            self._current_workflow)
        workflow.reset()
        self._current_workflow = workflow
        if self.callback:
            self.callback.startWorkflow(workflow)
        
    
    def addChildRec(self, obj, parent_id=None):
        workflow = self.currentWorkflow()
        id = obj.signature
        if id not in workflow.modules and parent_id:
            id = '%s/%s' % (parent_id, obj.signature)
        if obj.children:
            for child in obj.children:
                self.addChildRec(child, id)
            return
        if obj.signature in workflow.modules:
            # this is an already existing new-style job
            # mark that it have been used
            workflow.modules[obj.signature].mark()
            return
        if id in workflow.modules:
            # this is an already existing new-style job
            # mark that it have been used
            workflow.modules[id].mark()
            return
        # this is a new old-style job that we need to add
        self.addJob(id, {'__message__':obj.msg}, obj.name)
        
    def finishWorkflow(self):
        """ finish_job() -> None
        
            Finishes the running workflow

        """
        workflow = self._current_workflow
        # untangle parents
        for parent in workflow.parents.itervalues():
            self.addChildRec(parent)

        # Assume all unfinished jobs that were not updated are now finished
        for job in workflow.modules.values():
            if not job.finished and not job.updated:
                job.finish()
        if self.callback:
            self.callback.finishWorkflow(workflow)
        self._current_workflow = None
        self.save_to_file()
    
    def addJob(self, id, params=None, name='', finished=False):
        """ addJob(id: str, params: dict, name: str, finished: bool) -> uuid
        
            Adds a module to the current running workflow

        """
        workflow = self.currentWorkflow()
        if not workflow:
            return # ignore non-monitored jobs
        # we add workflows permanently if they have at least one job
        if not workflow.id in self._running_workflows:
            self._running_workflows[workflow.id] = workflow

        params = params if params is not None else {}

        if self.hasJob(id):
            # update job attributes
            job = self.getJob(id)
            job.parameters = params
            if name:
                job.name = name
            job.finished = finished
            # we want to keep the start date
        else:
            self._current_workflow.modules[id] = Module(id, params, name,
                                                            finished=finished)
        if self.callback:
            self.callback.addJob(self.getJob(id))

    def addParent(self, error):
        """ addParent(id: str, name: str, finished: bool) -> None
        
            Adds an exception to be used later

        """
        workflow = self.currentWorkflow()
        if not workflow:
            return # ignore non-monitored jobs
        # only keep the top item
        if error.children:
            for child in error.children:
                if id(child) in workflow.parents:
                    del workflow.parents[id(child)]
        workflow.parents[id(error)] = error

    def setCache(self, id, params, name=''):
        self.addJob(id, params, name, True)

    def checkJob(self, module, id, monitor):
        """ checkJob(module: VistrailsModule, id: str, monitor: instance) -> None
            Starts monitoring the job for the current running workflow
            module - the module to suspend
            id - the job identifier
            monitor - a class instance with a finished method for 
                      checking if the job has completed

        """
        if not self.currentWorkflow():
            if not monitor or not self.isDone(monitor):
                raise ModuleSuspended(module, 'Job is running', queue=monitor,
                                      job_id=id)
        job = self.getJob(id)
        if self.callback:
            self.callback.checkJob(module, id, monitor)
            return

        conf = get_vistrails_configuration()
        interval = conf.jobCheckInterval
        if interval and not conf.jobAutorun:
            if monitor:
                # wait for module to complete
                try:
                    while not self.isDone(monitor):
                        time.sleep(interval)
                        print ("Waiting for job: %s," 
                               "press Ctrl+C to suspend") % job.name
                except KeyboardInterrupt, e:
                    raise ModuleSuspended(module, 'Interrupted by user, job'
                                           ' is still running', queue=monitor,
                                           job_id=id)
        else:
            if not monitor or not self.isDone(monitor):
                raise ModuleSuspended(module, 'Job is running', queue=monitor,
                                      job_id=id)

    def getJob(self, id):
        """ getJob(id: str) -> Module
        
            Checks if a module exists using its id and returns it

        """
        if not self._current_workflow:
            return None
        return self._current_workflow.modules.get(id, None)

    def getCache(self, id):
        """ getCache(id: str) -> Module
            Checks if a completed module exists using its id and returns it
        """
        if not self._current_workflow:
            return None
        job = self._current_workflow.modules.get(id, None)
        if not job:
            return None
        return job if job.finished else None

    def hasJob(self, id):
        """ hasJob(id: str) -> bool
        
            Checks if a module exists

        """
        if not self._current_workflow:
            return None
        return id in self._current_workflow.modules
    
    def updateUrl(self, new, old):
        for workflow in self._running_workflows.values():
            if workflow.vistrail == old:
                workflow.vistrail = new

    def isDone(self, monitor):
        """ isDone(self, monitor) -> bool

            A job is done when it reaches finished or failed state
            val() is used by stable batchq branch
        """
        finished = monitor.finished()
        if type(finished)==bool:
            if finished:
                return True
        else:
            if finished.val():
                return True
        if hasattr(monitor, 'failed'):
            failed = monitor.failed()
            if type(failed)==bool:
                if failed:
                    return True
            else:
                if failed.val():
                    return True
        return False

##############################################################################
# Testing


class TestJob(unittest.TestCase):

    def test_job(self):
        job = JobMonitor.getInstance()
        module1 = Module('`13/5', {'a':3, 'b':'7'})
        module2 = Module('3', {'a':6}, 'my_name', 'a_string_date', True)
        # test module to/from dict
        module3 = Module.from_dict(module2.to_dict())
        self.assertEqual(module2, module3)
        
        workflow1 = Workflow('a.vt', 26)
        workflow2 = Workflow('b.vt', 'tagname', 'myjob', 'myid', 'tommy',
                             '2013-10-07 13:06',
                             {module1.id: module1, module2.id: module2})
        # test workflow to/from dict
        workflow3 = Workflow.from_dict(workflow2.to_dict())
        self.assertEqual(workflow2, workflow3)

        # test start/finish job
        job.startWorkflow(workflow2)
        self.assertEqual(workflow2, job._current_workflow)
        job.finishWorkflow()
        self.assertEqual(None, job._current_workflow)

        # test add job
        job.startWorkflow(workflow2)
        job.addJob('my_uuid_id', {'myparam': 0})
        self.assertIn('my_uuid_id', workflow2.modules)
        job.finishWorkflow()
        
        # test serialization
        job._running_workflows[workflow1.id] = workflow1
        job._running_workflows[workflow2.id] = workflow2
        job.save_to_file()
        job.load_from_file()
        self.assertIn(workflow1.id, job._running_workflows)
        self.assertIn(workflow2.id, job._running_workflows)
        self.assertEqual(workflow1, job._running_workflows[workflow1.id])
        self.assertEqual(workflow2, job._running_workflows[workflow2.id])
        job._running_workflows = dict()
