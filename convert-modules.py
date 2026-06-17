import os
import re
import sys
import subprocess
from argparse import ArgumentParser
import stat


def _top_level_bind_dir(path):
    abs_path = os.path.abspath(path)
    parts = abs_path.split(os.sep)

    if len(parts) > 1 and parts[1]:
        return os.sep + parts[1]

    return os.sep


def get_bind_dirs(path=None):
    if path is None:
        path = os.getcwd()

    bind_dirs = []
    for candidate in (path, os.path.realpath(path)):
        bind_dir = _top_level_bind_dir(candidate)
        if bind_dir not in bind_dirs:
            bind_dirs.append(bind_dir)

    return bind_dirs

def is_binary_executable(file_path):
    # Check if the file exists and is a regular file
    if not os.path.isfile(file_path):
        return False

    try:
        isascii = os.popen("file "+file_path+" | /usr/bin/grep ASCII").read().strip()
        if re.search("ASCII",isascii):
            return False
        else:
            return True

    except OSError:
        pass

    return False

def get_binary_executables(dirpath):
    # List files that are executable binaries
    file_list = os.listdir(dirpath)
    binary_executables = [file for file in file_list if is_binary_executable(os.path.join(dirpath,file))]

    return binary_executables


def read_envs_from_file(file_path):
    """
    Read environment variables from a text file with one per line.
    
    :param file_path: str, The path to the file containing environment variable names.
    :return: list, A list of environment variable names to be replaced.
    """
    envs_to_modify = []
    try:
        with open(file_path, 'r') as f:
            for line in f:
                env_name = line.strip()
                if env_name:
                    envs_to_modify.append(env_name)
        return envs_to_modify
    except FileNotFoundError:
        print(f"File not found: {file_path}")
        return []

def modify_lua_content(content, envs_to_modify, compiler_type):
    """
    Modify environment variable references in Lua content by prepending APPTAINERENV_.
    
    :param content: str, The Lua file content as a string.
    :param envs_to_modify: list, Environment variable names to be prefixed.
    :param compiler_type: str, Defines which compiler was used to build the spack-stack.
    :return: str, The modified Lua file content.
    """

    """
    Determine if system is running singularity or apptainer
    """

    output = subprocess.check_output(["singularity", "help"]).decode("utf-8")
    global env_regex
    if 'apptainer' in output:
      env_regex = "APPTAINERENV_"
    else:
      env_regex = "SINGULARITYENV_"
    for env in envs_to_modify:
        # Create regex pattern for variables with double quotes
        pattern = rf'"{env}"'
        modified_content = re.sub(pattern, f'"{env_regex}{env}"', content)
        if modified_content != content:
            content = modified_content
    
    # Iterate over each line in the content
    modified_content_lines = []
    local_path = args.output_dir+"/bin"
    command = "singularity exec -B "+basepath+" $img cp /opt/container-scripts/make-external ."
    os.system(command)
    for line in content.split('\n'):
    # check to see if the path is being set in the modulefile
        pattern = rf'"{env_regex}PATH"'
        match = re.search(pattern,line)
        new_pattern = os.getcwd()
        if match:
           # fix for spack-stack v1.9.2 container since it has two stack paths
           if(compiler_type == "intel"):
             new_line = re.sub(r'"([^"]*)\s*(?=intel)', f'"{new_pattern}/', line)
           elif(compiler_type == "gcc"):
             new_line = re.sub(r'"([^"]*)\s*(?=gcc)', f'"{new_pattern}/', line)
           else:
             new_line = re.sub(r'"([^"]*)\s*(?=oneapi)', f'"{new_pattern}/', line)
#          new_line = re.sub(r'"([^"]*)\s*(?=' + re.escape(compiler_type) + ')', f'"{new_pattern}/"', line)
           new_line = re.sub(pattern, '"PATH"', new_line)
           parts = new_line.split('"')
           bindir = parts[3]
           parts = line.split('"')
           containerdir = parts[3]
           print("checking bindir of ",bindir)
           # create the same directory on the local host
           host_root_dir=os.path.abspath(os.path.join(bindir, "../.."))
           container_root_dir=os.path.abspath(os.path.join(containerdir, ".."))
           command="singularity exec -B "+basepath+" "+args.img+" mkdir -p "+bindir
           print(command)
           os.system(command)
           # copy in all the files from the container to the host
           command = "singularity exec -B "+basepath+" "+args.img+" cp -r "+container_root_dir+" "+host_root_dir
           print(command)
           os.system(command)
           print("container bindir is ",containerdir)
           # now externalize the executables in that directory on the host
           if(os.path.exists(bindir)):
             binary_files = get_binary_executables(bindir)
             print(binary_files)
             for binfile in binary_files:
               command = "./make-external "+os.path.join(bindir,binfile)
               os.system(command)
           content += new_line
           break

    return content


def copy_and_modify_lua_files(output_dir, vars_file, compiler_type):
    """
    Copy all Lua files from the source directory to a new output directory,
    modifying them by prepending APPTAINERENV_ or SINGULARITYENV to specified environment variables.
    
    :param output_dir: str, The path to the output directory where modified Lua files will be saved.
    :param vars_file: str, The path to the file containing environment variable names.
    :param compiler_type: str, Defines which compiler was used to build the spack-stack.
    """
    source_dir = "./modulefiles"
    print("running copy and modify")
    try:
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # Read contents of the lua file
        for root, _, files in os.walk(source_dir):
            for file in files:
                if file.endswith(".lua"):
                    file_path = os.path.join(root, file)
                    with open(file_path, 'r') as f:
                        content = f.read()
                    
                    # Call modify_lua_content function
                    modified_content = modify_lua_content(content, read_envs_from_file(vars_file),compiler_type)
                    
                    # Determine the output file path relative to the source directory
                    relative_path = os.path.relpath(file_path, source_dir)
                    output_file_path = os.path.join(output_dir, relative_path)
                    
                    # Ensure the correct parent directories exist
                    os.makedirs(os.path.dirname(output_file_path), exist_ok=True)
                    
                    with open(output_file_path, 'w') as f:
                        f.write(modified_content)
        
        print("Modified Lua files have been saved to the specified output directory.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    parser = ArgumentParser(description="Modify Lua environment variable references")
    parser.add_argument("-i", "--container-image", dest="img", required=True,
                        help="Path to the singularity image file containing spack-stack")
    parser.add_argument("-o", "--output-dir", dest="output_dir", required=True,
                        help="Path to the output directory for modified Lua files")
    parser.add_argument("--host-compilers", action='store_true', dest="host_compilers", required=False,
                        help="Sync up the host Intel compilers and Intel MPI with the container spack-stack")
    parser.add_argument("-s", "--sandbox-compilers", dest="sandbox_compilers", required=False,
                        help="Path to Intel compilers sandbox")
    parser.add_argument("-d", "--bind-dirs", dest="bind_dirs", required=False,
                        help="Dir(s) separated by comma that need to be binded to the container")

    args = parser.parse_args()
    # set the img as an environment variable
    os.environ['img'] = args.img
    # include both logical and real paths so symlinked drives still bind correctly
    base_bind_dirs = get_bind_dirs()
    basepath = ",".join(base_bind_dirs)+" "

    # Ensure only one argument is used
    if args.host_compilers is True and args.sandbox_compilers is not None:
        print("Both compiler options are set. Please set one or the other!")
        sys.exit(1)

    # Copy out the dir conf file
    command = "singularity exec -e -B "+basepath+args.img+" cp -r /opt/container-scripts/bind_directories.conf ."
    os.system(command)

    # Set bind dir for gen-build-tools.sh
    if args.bind_dirs is not None:
        # update dir conf file with init dirs
        os.system("sed -i 's|INIT_LOCAL_DIRS=\(.*\)|INIT_LOCAL_DIRS="+args.bind_dirs+"|g' bind_directories.conf")

        # convert arg to a list
        bind_dirs_lst = [bd.strip().lstrip("/") for bd in args.bind_dirs.split(",") if bd.strip()]
        # add base bind dir(s) if not in list
        for base_dir in base_bind_dirs:
            base_dir_name = base_dir.lstrip("/")
            if base_dir_name and base_dir_name not in bind_dirs_lst:
                bind_dirs_lst.append(base_dir_name)
        # create dirs_cmd var
        dirs_cmd=""
        for bd in bind_dirs_lst:
            dirs_cmd="-B /{0} {1}".format(bd, dirs_cmd)
    else:
       dirs_cmd="-B {0}".format(basepath)
    
    # get the spack-stack version
    command =  'singularity exec $img ls /opt/spack-stack'
    spack_stack_ver = os.popen(command).read().strip()
    # get env name
    command =  "singularity exec $img ls /opt/spack-stack/"+spack_stack_ver+"/envs/"
    spack_stack_env = os.popen(command).read().strip()
    # copy the all the modulefiles out of the container image
    command = "singularity exec -e -B "+basepath+args.img+" cp -r /opt/spack-stack/"+spack_stack_ver+"/envs/"+spack_stack_env+"/install/modulefiles ."
    print(command)
    os.system(command)

    # get the stack type (intel v oneapi v gcc)
    stack_type=os.popen("ls ./modulefiles/Core").read().strip()
    compiler_type=stack_type.split("-")[1]

    # Copy over gnu and openmpi to a newly created dir, if it is the gnu spack-stack
    if compiler_type == "gcc" and spack_stack_env == "ufs-wm-env":
        os.makedirs("modulefiles/container-software/modulefiles")
        command = "singularity exec -e -B "+basepath+args.img+" cp -r /opt/modulefiles/gnu modulefiles/container-software/modulefiles"
        os.system(command)
        command = "singularity exec -e -B "+basepath+args.img+" cp -r /opt/modulefiles/openmpi modulefiles/container-software/modulefiles"
        os.system(command)

#   command = "singularity exec -e -B "+basepath+args.img+" cp -r /opt/spack-stack/"+spack_stack_ver+"/envs/unified-env/install/"+compiler_type+" ."
#   os.system(command)

    # get a list of all the files that contain either setenv, or _path
    os.system("/usr/bin/grep -R setenv modulefiles/* | awk -F '\"' '{print $2}' | sort | uniq > .envs")
    os.system("/usr/bin/grep -R _path modulefiles/* | awk -F '\"' '{print $2}' | sort | uniq >> .envs")
    os.system("sed -i '/MODULEPATH/d' .envs")
    # walk through all the files and change variables to contain APPTAINERENV_ or SINGULARITYENV_
    copy_and_modify_lua_files(args.output_dir, ".envs", compiler_type)

    # get the original module path from the lua file
    command = '/usr/bin/grep MODULEPATH ./modulefiles/Core/'+stack_type+'/*.lua | awk -F \'"\' \'{print $4}\''
    # Split if we have more than one spack-stack location
    spack_stack_path = os.popen(command).read().strip().split("\n")
    # Loop through list
    for ss_path in spack_stack_path:
        #print(ss_path)
        parts = ss_path.split('/')
        modulefiles_index = parts.index("modulefiles")
        parts[:modulefiles_index + 1] = [args.output_dir]
        new_path = '/'.join(parts)
        #print(f"new_path: {new_path}")
        command ="/usr/bin/grep -R -l MODULEPATH "+args.output_dir+"/Core | xargs sed -i 's|"+ss_path+"|"+new_path+"|g'"
        os.system(command)

    # get the origin module path for the mpi module
    command = '/usr/bin/grep -R MODULEPATH ./modulefiles/'+compiler_type+' | awk -F \'"\' \'{print $4}\' | head -n 1'
    mpi_stack_path = os.popen(command).read().strip()
    # hack to get this working
    if compiler_type == "oneapi" and spack_stack_env == "unified-env":
        mpi_stack_path = re.sub("fms-2024.01","unified-env",mpi_stack_path)

    print("using this modulepath to grep",mpi_stack_path)
    # replace the original path with the new path on the host system
    parts = mpi_stack_path.split('/')
    modulefiles_index = parts.index("modulefiles")
    parts[:modulefiles_index + 1] = [args.output_dir]
    new_path = '/'.join(parts)
    command ="/usr/bin/grep -R -l MODULEPATH "+args.output_dir+"/"+compiler_type+" | xargs sed -i 's|"+mpi_stack_path+"|"+new_path+"|g'"
    print("running this command for modulepath ",command)
    os.system(command)

    # set some basic paths inside the container that also include the location of ifort, icc, and icpc
    lua_file_path = args.output_dir+"/Core/"+stack_type+"/*.lua"
    container_path = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/local"

    command = "/usr/bin/grep ENV_F77 "+lua_file_path+" | awk -F '\"' '{print $4}' | xargs dirname"
    container_path = container_path+":"+os.popen(command).read().strip()
    command = "/usr/bin/grep ENV_CC "+lua_file_path+" | awk -F '\"' '{print $4}' | xargs dirname"
    container_path = container_path+":"+os.popen(command).read().strip()

    stack_intel_lua_file = args.output_dir+'/Core/'+stack_type+'/*.lua'
    command = f"sed -i '/prereq/a setenv(\"{env_regex}PATH\",\""+container_path+"\")' "+stack_intel_lua_file
    os.system(command)

    # some lua systems are incompatable with depends_on, so change that to load. It is slower, but works
    #command = "/usr/bin/grep -Ri -l depends_on "+args.output_dir+"/* | xargs sed -i 's/depends_on/load/g'"
    #os.system(command)

    # set path on host system to $PWD/args.output_dir/bin, which is where the gen tools will be placed
    # add img to the stack-intel/oneapi module as well
    local_path = args.output_dir+"/bin"
    os.system("mkdir "+local_path)
    new_line = 'prepend_path("PATH","'+local_path+'")'
    sed_command = f'sed -i \'/ENV_PATH/a {new_line}\' {stack_intel_lua_file}'
    os.system(sed_command)
    new_line = 'setenv("img","'+args.img+'")'
    sed_command = f'sed -i \'/ENV_PATH/a {new_line}\' {stack_intel_lua_file}'
    os.system(sed_command)

    # put make-external in the bin path
    command = "singularity exec -B "+basepath+" $img cp /opt/container-scripts/make-external "+local_path
    os.system(command)

    # generate the build tools locally in $PWD/bin. This path will be added to the path set in stack-intel module
    command = "singularity exec "+dirs_cmd+" -e $img /opt/container-scripts/gen-build-tools.sh -e "+local_path
    os.system(command)
    os.system("rm -rf ./modulefiles")
    os.system("rm ./make-external")
    
    command = "echo $(find "+args.output_dir+" -iname netcdf-c)/*"
    luafile = os.popen(command).read().strip()
    os.system("echo >> "+luafile)
    command = "cat "+luafile+" | /usr/bin/grep ENV_LD_LIBRARY_PATH | sed 's/LD_LIB/LIB/g' >>"+luafile
    os.system(command)

    # Check if using external compilers
    if args.host_compilers is True:
        cmd_ln_arg = ""
    elif args.sandbox_compilers is not None:
        cmd_ln_arg = f"-s {args.sandbox_compilers}"
    else:
        print("Using container compilers.\nDONE")
        sys.exit(1)

    # Update compilers info in spack-stack lua files
    command = "singularity exec -B "+basepath+" $img cp /opt/container-scripts/update_ss_container_compilers.sh ."
    os.system(command)
    command = f"./update_ss_container_compilers.sh -o {args.output_dir} {cmd_ln_arg}"
    os.system(command)
