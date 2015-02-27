# -*- coding: utf-8 -*-
# 
# Copyright (C) University College London, 2007-2012, all rights reserved.
# 
# This file is part of HemeLB and is CONFIDENTIAL. You may not work 
# with, install, use, duplicate, modify, redistribute or share this
# file, or any part thereof, other than as allowed by any agreement
# specifically made by you with University College London.
# 

import os.path
import cPickle
from copy import copy
import numpy as np
import yaml

from vtk import vtkSTLReader

from HemeLbSetupTool.Util.Observer import Observable
from HemeLbSetupTool.Model.SideLengthCalculator import AverageSideLengthCalculator
from HemeLbSetupTool.Model.Vector import Vector
from HemeLbSetupTool.Model.Iolets import ObservableListOfIolets, IoletLoader

class LengthUnit(Observable):
    def __init__(self, sizeInMetres, name, abbrv):
        self.SizeInMetres = sizeInMetres
        self.Name = name
        self.Abbrv = abbrv
        return 
    pass

metre = LengthUnit(1., 'metre', 'm')
millimetre = LengthUnit(1e-3, 'millimetre', 'mm')
micrometre = micron = LengthUnit(1e-6, 'micrometre', u'µm')

class Profile(Observable):
    """This class represents the parameters necessary to perform a
    setup for HemeLb and supplies the functionality to do it.

    The required parameters are below with defaults and all must be
    specified to actually create the setup files.
    
    """
    # Required parameters and defaults.
    _CloneOrder = ['StlFileUnitId', 'StlFile', 'VoxelSize']
    _Args = {'StlFile': None,
             'StlFileUnitId': 1,
             'Iolets': ObservableListOfIolets(),
             'VoxelSize': 0.,
             'TimeStepSeconds': 1e-4,
             'DurationSeconds': 5.0,
             'SeedPoint': Vector(),
             'OutputGeometryFile': None,
             'OutputXmlFile': None}
    _UnitChoices = [metre, millimetre, micrometre]
    
    def __init__(self, **kwargs):
        """Required arguments may be set here through keyword arguments.
        """
        # Set attributes on this instance according to the keyword
        # args given here or the default dict if they aren't present.
        for a, default in Profile._Args.iteritems():
            setattr(self, a,
                    kwargs.pop(a, copy(default)))
            continue
        # Raise an error on a kwarg we don't understand
        for k in kwargs:
            raise TypeError("__init__() got an unexpected keyword argument '%'" % k)

        # We need a reader to get the polydata
        self.StlReader = vtkSTLReader()
        
        # And a way to estimate the voxel size
        self.SideLengthCalculator = AverageSideLengthCalculator()
        self.SideLengthCalculator.SetInputConnection(self.StlReader.GetOutputPort())

        # Dependencies for properties
        self.AddDependency('HaveValidStlFile', 'StlFile')
        self.AddDependency('HaveValidOutputXmlFile', 'OutputXmlFile')
        self.AddDependency('HaveValidOutputGeometryFile', 'OutputGeometryFile')
        self.AddDependency('HaveValidSeedPoint', 'SeedPoint.x')
        self.AddDependency('HaveValidSeedPoint', 'SeedPoint.y')
        self.AddDependency('HaveValidSeedPoint', 'SeedPoint.z')
        self.AddDependency('IsReadyToGenerate', 'HaveValidStlFile')
        self.AddDependency('IsReadyToGenerate', 'HaveValidOutputXmlFile')
        self.AddDependency('IsReadyToGenerate', 'HaveValidOutputGeometryFile')
        self.AddDependency('IsReadyToGenerate', 'HaveValidSeedPoint')
        self.AddDependency('StlFileUnit', 'StlFileUnitId')
        self.AddDependency('VoxelSizeMetres', 'VoxelSize')
        self.AddDependency('VoxelSizeMetres', 'StlFileUnit.SizeInMetres')
        
        # When the STL changes, we should reset the voxel size and
        # update the vtkSTLReader.
        self.AddObserver('StlFile', self.OnStlFileChanged)
        return
    
    def UpdateAttributesBasedOnCmdLineArgs(self, cmdLineArgsDict):
        """ Helper method that takes a dictionary with the arguments provided 
        to the setup tool via command line (cmdLineArgsDict) and sets/updates 
        the relevant class attributes.
        """
        # Some attributes need to be set in a given order to avoid side effects. 
        # Set them first
        for attrName in self._CloneOrder:
            if attrName in cmdLineArgsDict:
                val = cmdLineArgsDict[attrName]
                if val is not None:
                    setattr(self, attrName, val)
                    cmdLineArgsDict.pop(attrName)

        # Set the rest
        for k, val in cmdLineArgsDict.iteritems():
            if val is not None:
                setattr(self, k, val)

    
    def OnStlFileChanged(self, change):
        self.StlReader.SetFileName(self.StlFile)
        self.VoxelSize = self.SideLengthCalculator.GetOutputValue()
        return
        
    @property
    def HaveValidStlFile(self):
        """Read only property indicating if our STL file is valid.
        """
        return IsFileValid(self.StlFile, ext='.stl', exists=True)

    @property
    def HaveValidSeedPoint(self):
        if np.isfinite(self.SeedPoint.x) and np.isfinite(self.SeedPoint.y) and np.isfinite(self.SeedPoint.z):
            return True
        return False
    
    @property
    def HaveValidOutputXmlFile(self):
        return IsFileValid(self.OutputXmlFile, ext='.xml')
    @property
    def HaveValidOutputGeometryFile(self):
        return IsFileValid(self.OutputGeometryFile, ext='.gmy')
    
    @property
    def IsReadyToGenerate(self):
        """Read only property indicating if we have enough information
        to do the setup.
        """
        if not self.HaveValidSeedPoint:
            return False
        if not self.HaveValidOutputXmlFile:
            return False
        if not self.HaveValidOutputGeometryFile:
            return False
        if not self.HaveValidStlFile:
            return False
        return True
    
    @property
    def StlFileUnit(self):
        return self._UnitChoices[self.StlFileUnitId]
    
    @property
    def VoxelSizeMetres(self):
        return self.VoxelSize * self.StlFileUnit.SizeInMetres
    @VoxelSizeMetres.setter
    def VoxelSizeMetres(self, value):
        self.VoxelSize = value / self.StlFileUnit.SizeInMetres
        return
    
    def LoadFromFile(self, filename):
        root, ext = os.path.splitext(filename)
        if ext == '.pro':
            return self.LoadProfileV1(filename)
        elif ext == '.pr2':
            return self.LoadProfileV2(filename)
        else:
            raise ValueError("Unexpected extension on profile file: " + ext)
        
    def LoadProfileV2(self, filename):
        state = yaml.load(file(filename))
        self.LoadFrom(state)
        return
    
    def LoadProfileV1(self, filename):
        restored = cPickle.Unpickler(file(filename)).load()
        restored._ResetPaths(filename)
        self.CloneFrom(restored)
        return
    
    def _ResetPaths(self, filename):
        # Now adjust the paths of filenames relative to the Profile file.
        # Note that this will work if an absolute path has been pickled as
        # os.path.join will discard previous path elements when it gets an
        # absolute path. (Of course, this will only work if that path is
        # correct!)
        basePath = os.path.dirname(os.path.abspath(filename))
        self.StlFile = os.path.abspath(
            os.path.join(basePath, self.StlFile)
        )
        self.OutputGeometryFile = os.path.abspath(
            os.path.join(basePath, self.OutputGeometryFile)
        )
        self.OutputXmlFile = os.path.abspath(
            os.path.join(basePath, self.OutputXmlFile)
        )
        return
    
    def Save(self, filename):
        basePath = str(os.path.dirname(filename))
        state = self.Yamlify()
        state['StlFile'] = os.path.relpath(state['StlFile'], basePath)
        state['OutputXmlFile'] = os.path.relpath(state['OutputXmlFile'], basePath)
        state['OutputGeometryFile'] = os.path.relpath(state['OutputGeometryFile'], basePath)
        with file(filename, 'w') as outfile:
            yaml.dump(state, stream=outfile)
            
        return
    
    def Generate(self):
        from HemeLbSetupTool.Model.OutputGeneration import PolyDataGenerator
        generator = PolyDataGenerator(self)
        generator.Execute()
        return
    
    def ResetVoxelSize(self, ignored=None):
        """Action to reset the voxel size to its default value.
        """
        self.VoxelSize = self.SideLengthCalculator.GetOutputValue()
        return
       
    pass
    
def IsFileValid(path, ext=None, exists=None):
    if not isinstance(path, (str, unicode)):
        return False
    if path == '':
        return False
    
    if exists is not None:
        if os.path.exists(path) != exists:
            return False
        pass
    
    if ext is not None:
        ending = os.path.splitext(path)[1]
        if ending != ext:
            return False
        pass
    return True
