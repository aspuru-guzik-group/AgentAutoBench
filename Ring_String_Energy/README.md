Save these scripts into the final result folder that is generated from elagenteworkdir, and make sure to replace the root_dir into the corresponding root directory for the result folder

1. Run the General_Boolean.py first, to extract the 8 key properties from the ORCA input file and ORCA output file for each molecule, and save into a .csv file. 

2. Run the RSE_referenced_value_generator.py, to generate the referenced value for the calculation. 

3. Run the RSE_specific.py, which to extract the delta-G value of ring string energy and comared with the referenced value generated in step 2, and calculate the error rate of these values. 

4. Run the RSE_Score_Generator.py, which generate the overall score for this benchmarking. 
