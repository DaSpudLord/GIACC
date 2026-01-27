# +-+-+ +-+-+-+-+ +-+-+-+-+
# |D|A| |S|P|U|D| |L|O|R|D|
# +-+-+ +-+-+-+-+ +-+-+-+-+

from enum import Enum
import mmap
import os
import struct
import sys
from typing import NamedTuple



#----- DIAGNOSTIC FUNCTIONS -----#



def error(msg):
    print("ERROR:", msg, file = sys.stderr)
    
    sys.exit(1)

def error_file_invalid(path):
    error(f"Input file is not a valid GIA file: \"{path}\"")

def bad_argv(msg, op_name = None):
    sys.stderr.write("INVALID ARGUMENTS")
    if op_name != None:
        sys.stderr.write(f" to \"{op_name}\"")
    
    print(":", msg, file = sys.stderr)
    
    print(file = sys.stderr)
    print_usage(op_name, verbose = 0, dst = sys.stderr)
    
    sys.exit(2)

def print_usage(op_name = None, verbose = 1, dst = sys.stdout):
    print("Usage:", file = dst)
    
    for op in Operations:
        op.print_usage(op_name, verbose = verbose, dst = dst)



#----- FILE PARSING/CONVERSION -----#



class AssetMode(Enum):
    BEYOND  = 0
    CLASSIC = 1

class FileType(Enum):
    GIP = 1
    GIL = 2
    GIA = 3
    GIR = 4

class Header(NamedTuple):
    Struct  = struct.Struct(">IIIII")   # big endian uint32_t x5
    
    FILE_LEN_EXCLUDED   = 4 # File length field does not count itself
    MAGIC_NUM   = 806   # Expected magic_num value - error if not equal to this
    
    file_len    : int
    file_ver    : int
    magic_num   : int
    file_type   : int
    content_len : int

class Footer(NamedTuple):
    Struct  = struct.Struct(">I")   # big endian uint32_t x1
    
    MAGIC_NUM   = 1657  # Expected magic_num value - error if not equal to this
    
    magic_num   : int

CLASSIC_MODE_TAG    = bytes.fromhex("20 01");
FILENAME_TERMINATOR = bytes.fromhex("2A 05");



def do_giacc_convert(src_path, to_mode, dst_path):
    
    #----- PARSE INPUT FILE -----#
    
    try:
        if to_mode != None and dst_path == None:
            # Destination is same as src, so open in read-write mode
            open_flags  = os.O_RDWR
            mmap_access = mmap.ACCESS_WRITE
        else:
            # We only need read access to src
            # (either because we aren't doing conversion, or conversion dst is different from src)
            open_flags  = os.O_RDONLY
            mmap_access = mmap.ACCESS_READ   # we gotta manually specify this otherwise mmap gets pissy
        
        if os.name == "nt":
            # only available/needed on windows
            open_flags |= os.O_BINARY
        
        src_fd  = os.open(src_path, open_flags) # mmap takes a file descriptor
        with mmap.mmap(src_fd, 0, access = mmap_access) as src:
            
            header  = Header._make(Header.Struct.unpack_from(src, 0))
            # Validate header
            if header.file_len != (len(src) - Header.FILE_LEN_EXCLUDED):
                error_file_invalid(src_path)
            if header.magic_num != Header.MAGIC_NUM:
                error_file_invalid(src_path)
            if header.file_type != FileType.GIA.value:
                error_file_invalid(src_path)
            if header.content_len != (len(src) - Header.Struct.size - Footer.Struct.size):
                error_file_invalid(src_path)
        
            footer  = Footer._make(Footer.Struct.unpack(src[-Footer.Struct.size : ]))
            # Validate footer
            if footer.magic_num != Footer.MAGIC_NUM:
                error_file_invalid(src_path)
            
            # Find index of filename terminator, searching backwards from footer
            fterm_index  = src.rfind(FILENAME_TERMINATOR, 0, -Footer.Struct.size)
            if fterm_index < 0:
                error_file_invalid(src_path)
            
            # Expected index of classic mode tag
            ctag_index   = fterm_index - len(CLASSIC_MODE_TAG)
            
            # Check for classic mode tag
            if ctag_index >= Header.Struct.size and src[ctag_index : fterm_index] == CLASSIC_MODE_TAG:
                from_mode   = AssetMode.CLASSIC
            else:
                from_mode   = AssetMode.BEYOND
                ctag_index  = fterm_index
            
            print("This asset is", " already" if from_mode == to_mode else "", " for ", from_mode.name.title(), " Mode.", sep = "")
            
            if to_mode == None:
                # Only querying asset type, don't do any conversion
                return
            
            #----- WRITE OUTPUT FILE -----#
            
            if from_mode == to_mode:
                print("No changes will be made.")
                
                if dst_path == None:
                    # Destination is same as source - no action needed
                    pass
                
                else:
                    # Copy source to destination unmodified
                    with open(dst_path, "wb") as dst:
                        dst.write(src)
            else:
                print("Converting asset to", to_mode.name.title(), "Mode...")
                
                # Correct header length fields
                if to_mode == AssetMode.CLASSIC:
                    len_adjustment  = +len(CLASSIC_MODE_TAG)
                elif to_mode == AssetMode.BEYOND:
                    len_adjustment  = -len(CLASSIC_MODE_TAG)
                else:
                    raise ValueError()
                
                # New header
                header_new  = header._replace(
                    file_len    = header.file_len + len_adjustment,
                    content_len = header.content_len + len_adjustment)
                # New index for the filename terminator
                fterm_index_new = fterm_index + len_adjustment
                
                if dst_path == None:
                    # Write converted file back to input file
                    # (in this case, we just modify the mmap'd src in-place)
                    
                    len_old = len(src)
                    if to_mode == AssetMode.CLASSIC:
                        # Make room for the classic mode tag
                        src.resize(len_old + len_adjustment)    # First grow the file
                        src.move(fterm_index_new, fterm_index, len_old - fterm_index)   # Shift everything after the tag down
                        
                        src[ctag_index : ctag_index + len(CLASSIC_MODE_TAG)] = CLASSIC_MODE_TAG  # and write the tag
                    else:
                        # Delete the classic mode tag
                        src.move(fterm_index_new, fterm_index, len_old - fterm_index)   # Shift everything after the tag up
                        src.resize(len_old + len_adjustment)    # And shrink the file
                    
                    Header.Struct.pack_into(src, 0, *header_new) # Also rewrite the header
                    
                else:
                    # Copy to destination with classic mode tag added/removed
                    with open(dst_path, "wb") as dst:
                        
                        dst.write(Header.Struct.pack(*header_new))
                        
                        # Write everything before the classic mode tags
                        dst.write(src[Header.Struct.size : ctag_index])
                        
                        if to_mode == AssetMode.CLASSIC:
                            # Write the classic mode tag
                            dst.write(CLASSIC_MODE_TAG)
                        
                        # Everything else
                        dst.write(src[fterm_index : ])
        
    except OSError as e:
        error(e)
    
    # we did it yay
    print("Conversion completed.")
    return



#----- COMMAND-LINE INTERFACE -----#



# Base class of operations, which are the different commands that giacc accepts
class BaseOperation:
    def __init__(self, *forms, desc):
        self.__forms    = forms
        self.__desc = desc
    
    # Each operation has one or more forms
    def forms(self):
        return self.__forms
    def description(self):
        return self.__desc
    
    # Override in derived class to execute operation when invoked in command line
    # (but only if form does not have its own implementation)
    def __call__(self, form, op_name, *args):
        raise NotImplementedError()
    
    def print_usage(self, op_name = None, verbose = 1, dst = sys.stdout):
        matched = False
        
        for f in self.forms():
            if op_name == None or f.name() == op_name:
                f.print_form(dst = dst)
                matched = True
        
        if matched == True and verbose > 0:
            print("\t", self.description(), sep = "", file = dst)

# A form is the format that a command takes on the command line, identified by a name and possible parameters
class OperationForm:
    def __init__(self, op, name, *params, func = None):
        self.__oper = op
        self.__name = name
        self.__params   = params
        self.__func = func
    
    def operation(self):    # Operation that this form belongs to
        return self.__oper
    def name(self): # Name used to invoke the form on the command line
        return self.__name
    def parameters(self):   # Parameters passed to operation (list of strings)
        return self.__params
    # Multiple forms in the same operation may have the same name if they have different parameter counts
    
    # Override in derived class to execute operation when invoked in command line.
    # If not overridden, executes function passed to constructor (if any), or forwards to owning operation
    def __call__(self, op_name, *args):
        if self.__func != None:
            self.__func(*args)
        else:
            self.operation()(self, op_name, *args)
    
    def print_form(self, dst = sys.stdout):
        params  = (f"[{p}]" for p in self.parameters())
        print("> giacc.py", self.name(), *params, file = dst)



# to-classic or to-beyond
class ConvertOperation(BaseOperation):
    def __init__(self):
        # custom OperationForm subclass, stores AssetMode to convert to
        class FormConvertsTo(OperationForm):
            def __init__(self, op, to_mode):
                super().__init__(op, "to-" + to_mode.name.lower(), "input filename", "output filename")
                
                self.__to_mode  = to_mode
            
            def to_mode(self):
                return self.__to_mode
            
            def __call__(self, op_name, src_path, dst_path):
                if dst_path == "*":
                    dst_path    = None
                
                do_giacc_convert(src_path, self.to_mode(), dst_path)
        
        super().__init__(FormConvertsTo(self, AssetMode.CLASSIC), FormConvertsTo(self, AssetMode.BEYOND),
            desc = "Converts the GIA file at [input filename] to Classic Mode or Beyond Mode, respectively,"
                " and writes the converted file to [output filename]."
                " No changes are made if the input file is already configured for the target mode."
                " If the output file already exists, it is overwritten without warning."
                " If [output filename] is a single asterisk (\"*\"),"
                " the converted file is written back to the input file, overwriting the prior contents.")



# query [filename]
class QueryOperation(BaseOperation):
    def __init__(self):
        super().__init__(OperationForm(self, "query", "filename"),
            desc = "Tests whether [filename] denotes a Classic Mode asset file or Beyond Mode asset file."
                " No conversion is performed and the file is not modified.")
    
    def __call__(self, form, op_name, path):
        do_giacc_convert(path, None, None)



# help [command]
class HelpOperation(BaseOperation):
    def __init__(self):
        super().__init__(OperationForm(self, "help"), OperationForm(self, "help", "command"),
            desc = "Displays this usage message."
                " If [command] is given, displays the usage message just for the given command.")
    
    def __call__(self, form, op_name, help_op = None):
        print_usage(help_op)



# List of operations
Operations  = [
    ConvertOperation(),
    QueryOperation(),
    HelpOperation(),
]



if __name__ == "__main__":
    
    if len(sys.argv) < 2:
        bad_argv("Missing operation argument")
    
    op_name = sys.argv[1].casefold()
    op_argv = sys.argv[2 : ]
    op_argc = len(op_argv)
    
    # get list of forms with matching name
    forms   = [f for op in Operations for f in op.forms() if f.name() == op_name]
    
    if len(forms) == 0:
        # no matching forms
        bad_argv(f"Unknown operation \"{sys.argv[1]}\"")
    
    # find the form with the right number of parameters
    for f in forms:
        if len(f.parameters()) == op_argc:
            f(op_name, *op_argv)
            break
        
    else:
        # wrong number of parameters passed - generate error message
        if all(op_argc < len(f.parameters()) for f in forms):
            label   = "Too few"
        elif all(op_argc > len(f.parameters()) for f in forms):
            label   = "Too many"
        else:
            label   = "Incorrect number of"
        
        if len(forms) == 1:
            expected    = len(forms[0].parameters())
        else:
            if len(forms) > 2:
                oxford  = ","
            else:
                oxford  = ""
            
            expected    = ", ".join(str(len(f.parameters())) for f in forms[: -1])
            expected    = f"{expected}{oxford} or {len(forms[-1].parameters())}"
        
        bad_argv(f"{label} arguments (received {op_argc}, expected {expected})", op_name)



# +-+-+ +-+-+-+-+ +-+-+-+-+
# |D|A| |S|P|U|D| |L|O|R|D|
# +-+-+ +-+-+-+-+ +-+-+-+-+