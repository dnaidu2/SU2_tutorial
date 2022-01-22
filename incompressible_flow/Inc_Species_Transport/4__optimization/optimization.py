# FADO script: Shape Optimization with Species Variance OF

from FADO import *

# Design variables ----------------------------------------------------- #

nDV = 10
ffd = InputVariable(0.0,PreStringHandler("DV_VALUE="),nDV)
ffd = InputVariable(np.zeros((nDV,)),ArrayLabelReplacer("__FFD_PTS__"), 0, np.ones(nDV), -0.0075,0.0075)

# Parameters ----------------------------------------------------------- #

# The master config `configMaster.cfg` serves as an SU2 adjoint regression test.
# For a correct gradient validation we need to exchange some options

# switch from direct to adjoint mode and adapt settings.
enable_direct = Parameter([""], LabelReplacer("%__DIRECT__"))
enable_adjoint = Parameter([""], LabelReplacer("%__ADJOINT__"))
enable_not_def = Parameter([""], LabelReplacer("%__NOT_DEF__"))
enable_def = Parameter([""], LabelReplacer("%__DEF__"))

# Switch Objective Functions
OF_SpecVar = Parameter([""], LabelReplacer("%__OF_SpecVar__"))

# Evaluations ---------------------------------------------------------- #

# Define a few often used variables
ncores="2"
configMaster="species3_primitiveVenturi.cfg"
meshName="primitiveVenturi.su2"

# Note that correct SU2 version needs to be in PATH

def_command = "SU2_DEF " + configMaster
cfd_command = "mpirun -n " + ncores + " SU2_CFD " + configMaster

cfd_ad_command = "mpirun -n " + ncores + " SU2_CFD_AD " + configMaster
dot_ad_command = "mpirun -n " + ncores + " SU2_DOT_AD " + configMaster

max_tries = 1

# mesh deformation
deform = ExternalRun("DEFORM",def_command,True) # True means sym links are used for addData
deform.setMaxTries(max_tries)
deform.addConfig(configMaster)
deform.addData(meshName)
deform.addExpected("mesh_out.su2")
deform.addParameter(enable_def)

# direct run
direct = ExternalRun("DIRECT",cfd_command,True)
direct.setMaxTries(max_tries)
direct.addConfig(configMaster)
direct.addData("DEFORM/mesh_out.su2",destination=meshName)
direct.addData("solution.csv")
direct.addExpected("restart.csv")
direct.addParameter(enable_direct)
direct.addParameter(enable_not_def)

# adjoint run
adjoint = ExternalRun("ADJOINT",cfd_ad_command,True)
adjoint.setMaxTries(max_tries)
adjoint.addConfig(configMaster)
adjoint.addData("DEFORM/mesh_out.su2", destination=meshName)
# add all primal solution files
adjoint.addData("DIRECT/restart.csv", destination="solution.csv")
adjoint.addExpected("restart_adj_specvar.csv")
adjoint.addParameter(enable_adjoint)
adjoint.addParameter(enable_not_def)
adjoint.addParameter(OF_SpecVar)

# gradient projection
dot = ExternalRun("DOT",dot_ad_command,True)
dot.setMaxTries(max_tries)
dot.addConfig(configMaster)
dot.addData("DEFORM/mesh_out.su2", destination=meshName)
dot.addData("ADJOINT/restart_adj_specvar.csv", destination="solution_adj_specvar.csv")
dot.addExpected("of_grad.csv")
dot.addParameter(enable_def)
dot.addParameter(OF_SpecVar) # necessary for correct file extension

# Functions ------------------------------------------------------------ #

specVar = Function("specVar", "DIRECT/history.csv",LabeledTableReader("\"Species_Variance\""))
specVar.addInputVariable(ffd,"DOT/of_grad.csv",TableReader(None,0,(1,0))) # all rows, col 0, don't read the header
specVar.addValueEvalStep(deform)
specVar.addValueEvalStep(direct)
specVar.addGradientEvalStep(adjoint)
specVar.addGradientEvalStep(dot)
specVar.setDefaultValue(0.0)

# Driver --------------------------------------------------------------- #

driver = ScipyDriver()
#printDocumentation(driver.addObjective)
# min = minimization of OF
# avgT = function to be optimized
# 1.0 = scale, optimizer will see funcVal*scale, Can be used to scale the gradient from of_grad
driver.addObjective("min", specVar, 0.5)

driver.setWorkingDirectory("OPTIM")
#printDocumentation(driver.setEvaluationMode)
# True = parallel evaluation mode
# 2.0 = driver will check every 2sec whether it can start a new eval
driver.setEvaluationMode(False,2.0)
#printDocumentation(driver.setStorageMode)
# True = keep all designs
# DSN_ = folder prefix
driver.setStorageMode(True,"DSN_")
#printDocumentation(driver.setFailureMode)
# SOFT = if func eval fails, just the default val will be taken
driver.setFailureMode("SOFT")

his = open("optim.csv","w",1)
driver.setHistorian(his)

# Optimization, SciPy -------------------------------------------------- #

import scipy.optimize

driver.preprocess()
x = driver.getInitial()

options = {'disp': True, 'ftol': 1e-10, 'maxiter': 25}

optimum = scipy.optimize.minimize(driver.fun, x, method="SLSQP", jac=driver.grad,\
          constraints=driver.getConstraints(), bounds=driver.getBounds(), options=options)

his.close()

