#! /usr/bin/env python2
from verifyproblem import Problem,ProblemAspect,TestCaseGroup,Submissions,re_argument
from program import Program
import subprocess
import os
import re
import shutil
import logging
import sys
import random
from argparse import ArgumentParser, ArgumentTypeError
from pickcase import Picker

from timeit import default_timer as timer

class Fuzzer:
	RANDOMIZED_CASES=50
	MAX_FAILS = 5

	@staticmethod
	def _randomizeCase(original,randomized,cases,seed):
		with open(original, 'r') as f1:
			with open(randomized, 'w+') as f2:
				lines = f1.readlines()
				written = 0
				for i, line in enumerate(lines):
					if not line.startswith('#'):
						if written == 0:
							f2.write(str(cases) + "\n")
						elif written == 1:
							f2.write(seed + "\n")
						else:
							f2.write(line)
						written += 1

	FNULL = open(os.devnull, 'w')

	@staticmethod
	def _callmake(folder,rule):
		subprocess.call(["make",rule],stdout=Fuzzer.FNULL, stderr=subprocess.STDOUT,cwd=folder)

	@staticmethod
	def _cleanup(randomized):
		for ext in ['seed','in','ans']:
			if ext in randomized:
				if os.path.isfile(randomized[ext]):
					os.remove(randomized[ext])

	@staticmethod
	def _copyusefulstuff(failpath,tmpdir,randomized,failed):
		if failpath is not None:		
			for ext in ['seed','in','ans']:
				dest = os.path.join(failpath,"fail" + str(failed) + "." + ext)
				shutil.copy(randomized[ext], dest)
			output = os.path.join(tmpdir,"output")
			if os.path.isfile(output):
				outputdest = os.path.join(failpath,"fail" + str(failed) + ".out")
				shutil.copy(output, outputdest)
			feedbackdir = os.path.join(tmpdir,"lastfeedback")
			judgemessage = os.path.join(feedbackdir,"judgemessage.txt")
			if os.path.isfile(judgemessage):
				judgemessagedest = os.path.join(failpath,"fail" + str(failed) + ".judgemessage")
				shutil.copy(judgemessage, judgemessagedest)
			diffposition = os.path.join(feedbackdir,"diffposition.txt")
			if os.path.isfile(diffposition):
				diffpositiondest = os.path.join(failpath,"fail" + str(failed) + ".diffposition")
				shutil.copy(diffposition, diffpositiondest)


	@staticmethod
	def runRandomCase(args, logger):
		args.bail_on_error=False
		args.parts=["submissions"]
		ProblemAspect.silent=True

		Fuzzer._callmake(args.problemdir,"checker")
		with Problem(args.problemdir) as prob:
			randomized={}
			try:
				datadir = os.path.join(prob.probdir, 'data')
				secretdir = os.path.join(datadir, 'secret')
				casefile = os.path.join(secretdir,args.case + '.seed')

				if not os.path.isfile(casefile):
					logger.error('Could not locate seed file %s' % (casefile))
					return

				if args.failpath is not None:
					if not os.path.isdir(args.failpath):
						logger.error('fail destination is not a directory')
						return
					if not os.access(args.failpath, os.W_OK):
						logger.error('could not write to fail destination')
						return
					failpathWA=os.path.join(args.failpath,"wa")
					failpathRTE=os.path.join(args.failpath,"rte")
					if not os.path.isdir(failpathWA):
						os.mkdir(failpathWA)
					if not os.path.isdir(failpathRTE):
						os.mkdir(failpathRTE)

				program = Program(os.path.realpath(args.solution), prob.tmpdir)
				logger.info('Compiling program %s' % (program.name))

				if not program.compile():
					logger.error('Compile error for program %s' % (program.name))
					return


				#prepare the things we will need
				logger.info("preparing")
				Fuzzer._callmake(prob.probdir,"generator")
				Fuzzer._callmake(prob.probdir,"anysolution")
				
				picker = None
				FNULL = open(os.devnull, 'w')

				failedWA=0
				failedRTE=0
				logger.info('finished %s runs of %s on %s (%s failed)' % (0,args.runs, args.case, 0))
				for i in range(args.runs):
					seed=str(random.getrandbits(63))
					randomized={}
					for ext in ['seed','in','ans']:
						randomized[ext] = os.path.join(secretdir,args.case + "_" + seed + "." + ext)

					logger.debug("randomizing %s"%(args.case))
					Fuzzer._randomizeCase(casefile,randomized["seed"],Fuzzer.RANDOMIZED_CASES,seed)
					#generate in and out file
					Fuzzer._callmake(prob.probdir,randomized["in"])
					Fuzzer._callmake(prob.probdir,randomized["ans"])
					if picker is None:
						picker=Picker(randomized["in"])
					# subprocess.call(["cat",randomized["in"]])
					#update testdata
					testdata = TestCaseGroup(prob, os.path.join(prob.probdir, 'data'))
					
					#run problemtools
					logger.debug("preparing and running problem tools")
					args.data_filter=re_argument(args.case +"_" + seed)
					(result1, result2) = testdata.run_submission(program,args)

					if str(result1)[:2] == 'WA':
						logger.debug("found problematic input, picking failing case")
						feedbackdir = os.path.join(prob.tmpdir,"lastfeedback")
						judgemessage = os.path.join(feedbackdir,"judgemessage.txt")
						case = picker.pickcase(randomized["in"],Picker.firstfailingcase(judgemessage,randomized["ans"]))
						with open(randomized["in"],'w+') as f:
							for line in case:
								f.write(line)
						Fuzzer._callmake(prob.probdir,randomized["ans"])
						
						logger.debug("running program again on singular case")
						(result1, result2) = testdata.run_submission(program,args)

						failedWA += 1
						if str(result1)[:2] == 'WA':
							if args.failpath is not None:
								faildir=os.path.join(failpathWA,"fail" + str(failedWA))
								if os.path.isdir(faildir):
									log.error("%s already exists" % faildir)
									return
								os.mkdir(faildir)
								Fuzzer._copyusefulstuff(faildir,prob.tmpdir,randomized,failedWA)
							else:
								logger.info("found failing case:")
								with open(randomized['in']) as f:
									for line in f.readlines():
										logger.info(line)
						else :
							logger.info("Program has feedback errors between test cases (or outputs something after the correct answer)")
							if args.failpath is not None:
								faildir=os.path.join(failpathWA,"fail" + str(failedWA))
								if os.path.isdir(faildir):
									log.error("%s already exists" % faildir)
									return
								os.mkdir(faildir)

								Fuzzer._copyusefulstuff(faildir,prob.tmpdir,randomized,failedWA)
							return
							
					elif str(result1)[:2] == 'TL':
						logger.info("Program hit time limit")
						return
					elif str(result1)[:2] == 'JE':
						logger.info("Judge Error occurred")
						return
					elif str(result1)[:2] == 'RT':
						#binary search for the error
						logger.debug("Runtime error occurred, binary search for the test case")

						firsthalf = picker.splitcase(randomized["in"],True)
						secondhalf = picker.splitcase(randomized["in"],False)

						while firsthalf[0]!="0\n":
							with open(randomized["in"],'w+') as f:
								for line in firsthalf:
									f.write(line)
							Fuzzer._callmake(prob.probdir,randomized["ans"])
							
							logger.debug("running program again on half of remainder")
							(result1, result2) = testdata.run_submission(program,args)
							if str(result1)[:2] == 'RT':
								logger.debug("RTE occurred in first half")
							else:
								logger.debug("RTE occurred in second half")
								with open(randomized["in"],'w+') as f:
									for line in secondhalf:
										f.write(line)
							firsthalf = picker.splitcase(randomized["in"],True)
							secondhalf = picker.splitcase(randomized["in"],False)

						logger.debug("should have RTE case now")
						with open(randomized["in"],'w+') as f:
							for line in secondhalf:
								f.write(line)
						Fuzzer._callmake(prob.probdir,randomized["ans"])
						
						logger.debug("running program on RTE case")
						(result1, result2) = testdata.run_submission(program,args)
						
						failedRTE += 1
						if str(result1)[:2] == 'RT':
							logger.debug("RTE binary search successful")
							if args.failpath is not None:
								faildir=os.path.join(failpathRTE,"fail" + str(failedRTE))
								if os.path.isdir(faildir):
									log.error("%s already exists" % faildir)
									return
								os.mkdir(faildir)

								Fuzzer._copyusefulstuff(faildir,prob.tmpdir,randomized,failedRTE)
							else:
								logger.info("found RTE case:")
								with open(randomized['in']) as f:
									for line in f.readlines():
										logger.info(line)

						else:
							logger.info("RTE binary search unsuccessful, Program has feedback errors")
							if args.failpath is not None:
								faildir=os.path.join(failpathRTE,"fail" + str(failedRTE))
								if os.path.isdir(faildir):
									log.error("%s already exists" % faildir)
									return
								os.mkdir(faildir)

								Fuzzer._copyusefulstuff(failpathRTE,prob.tmpdir,randomized,failedRTE)
							return


					logger.info('finished %s runs of %s on %s (%s failed)' % (i+1,args.runs, args.case, failedWA+failedRTE))
					
					Fuzzer._cleanup(randomized)

					if failedWA+failedRTE >= Fuzzer.MAX_FAILS:
						logger.info('enough runs failed, ending run')
						return

			finally:
				Fuzzer._cleanup(randomized)
				Fuzzer._callmake(prob.probdir,"clean")

	@staticmethod
	def argparser():
		parser = ArgumentParser(description="Run randomized cases")
		parser.add_argument("-t", "--fixed_timelim", help="use this fixed time limit (useful in combination with -d and/or -s when all AC submissions might not be run on all data)", type=int)
		parser.add_argument("-l", "--log-level", dest="loglevel", help="set log level (debug, info, warning, error, critical)", default="info")
		parser.add_argument("-r", "--runs", dest="runs", help="set the number of runs", default=10)
		parser.add_argument("-c", "--case", dest="case", help="set the base case which is then randomized", default="small1")
		parser.add_argument("-f", "--failpath", dest="failpath",help="set the path where the failing cases should be stored", default=None)
		parser.add_argument('problemdir')
		parser.add_argument('solution')
		return parser

	@staticmethod
	def default_args():
		return Fuzzer.argparser().parse_args([None,None])


if __name__ == '__main__':
	args = Fuzzer.argparser().parse_args()
	#args.data_filter=re.compile(".*")
	args.data_filter=re.compile("data/" + args.case + "$")
	fmt = "%(levelname)s %(message)s"
	#silence verifyproblem
	logging.basicConfig(stream=sys.stdout,
	 					format=fmt,
	 					level=eval("logging.CRITICAL"))

	logger=logging.getLogger("fuzzylogger")
	logger.setLevel(eval("logging." + args.loglevel.upper()))

	Fuzzer.runRandomCase(args,logger)