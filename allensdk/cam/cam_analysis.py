# -*- coding: utf-8 -*-
"""
Created on Wed Dec 16 10:26:59 2015

@author: saskiad
"""

from allensdk.cam.static_grating import StaticGrating
from allensdk.cam.movie_analysis import LocallySN
from allensdk.cam.natural_images import NaturalImages
from allensdk.core.cam_nwb_data_set import CamNwbDataSet
from drifting_grating import DriftingGrating
from movie_analysis import MovieAnalysis
import CAM_plotting as cp
import argparse

class CamAnalysis(object):
    STIMULUS_A = 'A'
    STIMULUS_B = 'B'
    STIMULUS_C = 'C'

    def __init__(self, nwb_path, save_path, lims_id, area, depth):
        self.nwb = CamNwbDataSet(nwb_path)                        
        self.save_path = save_path
        self.lims_id = lims_id
        self.nwb.default_HVA = area
        self.nwb.default_depth = depth
    
    def save_stimulus_a(self, dg, nm1, nm3, peak):
        self.nwb.save_analysis_dataframes(
            ('stim_table_dg', dg.stim_table),
            ('sweep_response_dg', dg.sweep_response),
            ('mean_sweep_response_dg', dg.mean_sweep_response),
            ('peak', peak),        
            ('sweep_response_nm1', nm1.sweep_response),
            ('stim_table_nm1', nm1.stim_table),
            ('sweep_response_nm3', nm3.sweep_response))
        
        self.nwb.save_analysis_arrays(
            ('celltraces_dff', nm1.celltraces_dff),
            ('response_dg', dg.response),
            ('binned_cells_sp', nm1.binned_cells_sp),
            ('binned_cells_vis', nm1.binned_cells_vis),
            ('binned_dx_sp', nm1.binned_dx_sp),
            ('binned_dx_vis', nm1.binned_dx_vis))
    
        
    def save_stimulus_b(self, sg, nm1, ni, peak): 
        nwb = CamNwbDataSet(self.save_path)
        nwb.save_analysis_dataframes(
            ('stim_table_sg', sg.stim_table),
            ('sweep_response_sg', sg.sweep_response),
            ('mean_sweep_response_sg', sg.mean_sweep_response),
            ('sweep_response_nm1', nm1.sweep_response),
            ('stim_table_nm1', nm1.stim_table),
            ('sweep_response_ni', ni.sweep_response),
            ('stim_table_ni', ni.stim_table),
            ('mean_sweep_response_ni', ni.mean_sweep_response),
            ('peak', peak))

        nwb.save_analysis_arrays(
            ('celltraces_dff', nm1.celltraces_dff),
            ('response_sg', sg.response),
            ('response_ni', ni.response),
            ('binned_cells_sp', nm1.binned_cells_sp),
            ('binned_cells_vis', nm1.binned_cells_vis),
            ('binned_dx_sp', nm1.binned_dx_sp),
            ('binned_dx_vis', nm1.binned_dx_vis))
    
    
    def save_stimulus_c(self, lsn, nm1, nm2, peak):                
        nwb = CamNwbDataSet(self.save_path)
        nwb.save_analysis_dataframes(
            ('stim_table_lsn', lsn.stim_table),
            ('sweep_response_nm1', nm1.sweep_response),
            ('peak', peak),
            ('sweep_response_nm2', nm2.sweep_response),
            ('sweep_response_lsn', lsn.sweep_response),
            ('mean_sweep_response_lsn', lsn.mean_sweep_response))  
        
        nwb.save_analysis_arrays(
            ('receptive_field_lsn', lsn.receptive_field),
            ('celltraces_dff', nm1.celltraces_dff),
            ('binned_dx_sp', nm1.binned_dx_sp),
            ('binned_dx_vis', nm1.binned_dx_vis),    
            ('binned_cells_sp', nm1.binned_cells_sp),
            ('binned_cells_vis', nm1.binned_cells_vis))
    
    
    def stimulus_a(self, plot_flag=False, save_flag=True):
        dg = DriftingGrating(self)
        nm3 = MovieAnalysis(self, 'natural_movie_three')    
        nm1 = MovieAnalysis(self, 'natural_movie_one')        
        print "Stimulus A analyzed"
        peak = multi_dataframe_merge([nm1.peak_run, dg.peak, nm1.peak, nm3.peak])
        if plot_flag:
            cp.plot_3SA(dg, nm1, nm3)
            cp.plot_Drifting_grating_Traces(dg)
    
        if save_flag:
            self.save_stimulus_a(dg, nm1, nm3, peak)
    
    def stimulus_b(self, plot_flag=False, save_flag=True):
        sg = StaticGrating(self)    
        ni = NaturalImages(self)
        nm1 = MovieAnalysis(self, 'natural_movie_one')            
        print "Stimulus B analyzed"
        peak = multi_dataframe_merge([nm1.peak_run, sg.peak, ni.peak, nm1.peak])
                
        if plot_flag:
            cp.plot_3SB(sg, nm1, ni)
            cp.plot_NI_Traces(ni)
            cp.plot_SG_Traces(sg)
                    
        if save_flag:
            self.save_stimulus_b(sg, nm1, ni, peak)
    
    def stimulus_c(self, plot_flag=False, save_flag=True):
        nm2 = MovieAnalysis(self, 'natural_movie_two')
        lsn = LocallySN(self)
        nm1 = MovieAnalysis(self, 'natural_movie_one')
        print "Stimulus C analyzed"
        peak = multi_dataframe_merge([nm1.peak_run, nm1.peak, nm2.peak])
                
        if plot_flag:
            cp.plot_3SC(lsn, nm1, nm2)
            cp.plot_LSN_Traces(lsn)
    
        if save_flag:
            self.save_stimulus_c(lsn, nm1, nm2, peak)

def multi_dataframe_merge(dfs):
    out_df = None
    for i,df in enumerate(dfs):
        if out_df is None:
            out_df = df
        else:
            out_df = out_df.merge(df, left_index=True, right_index=True, suffixes=['','_%d' % i])
    return out_df
    
                    
def run_cam_analysis(stimulus, nwb_path, save_path,
                     lims_id=None, area=None, depth=None):   
    cam_analysis = CamAnalysis(nwb_path, save_path, lims_id, area, depth)

    if stimulus == CamAnalysis.STIMULUS_A:
        cam_analysis.stimulus_a(plot_flag=False)
    elif stimulus == CamAnalysis.STIMULUS_B:
        cam_analysis.stimulus_b(plot_flag=False)
    elif stimulus == CamAnalysis.STIMULUS_C:
        cam_analysis.stimulus_c(plot_flag=False)
    else:
        raise IndexError("Unknown stimulus: %s" % stimulus)
    
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_nwb", required=True)
    parser.add_argument("--output_nwb", default=None)

    # TODO: unhardcode
    parser.add_argument("--stimulus", default=CamAnalysis.STIMULUS_A)
    parser.add_argument("--depth", type=int, default=175)

    args = parser.parse_args()

    if args.output_nwb is None:
        args.output_nwb = args.input_nwb
    
    run_cam_analysis(args.stimulus, args.input_nwb, args.output_nwb, args.depth)


if __name__=='__main__': main()
    
