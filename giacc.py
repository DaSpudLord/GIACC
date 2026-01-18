# +-+-+ +-+-+-+-+ +-+-+-+-+
# |D|A| |S|P|U|D| |L|O|R|D|
# +-+-+ +-+-+-+-+ +-+-+-+-+

from collections import namedtuple
from enum import Enum
import mmap
import os
import struct
import sys



def error(msg):
    print("ERROR:", msg)
    sys.exit(1)

def bad_argv(msg):
    print("INVALID ARGUMENTS:", msg, file = sys.stderr)
    
    print(file = sys.stderr)
    print_help(verbose = 0, dst = sys.stderr)
    sys.exit(2)

def error_file_invalid(path):
    error("Input file is not a valid GIA file: \"" + path + "\"")

def print_help(verbose = 1, dst = None):
    print("Usage:", file = dst)
    
    print("> giacc.py to-classic [input filename] [output filename]", file = dst)
    print("> giacc.py to-beyond [input filename] [output filename]", file = dst)
    if verbose > 0:
        print("\tConverts the GIA file at the [input filename] to Classic Mode or Beyond Mode, respectively,",
            "and writes the converted file to [output filename].",
            "No changes are made if the input file is already configured for the target mode.",
            "If the output file already exists, it is overwritten without warning.",
            "If [output filename] is a single asterisk (\"*\"), the converted file is written back to the input file, overwriting the prior contents.",
            file = dst)
    
    print("> giacc.py query [filename]", file = dst)
    if verbose > 0:
        print("\tTests whether the [filename] denotes a Classic Mode asset file or Beyond Mode asset file.",
            "No conversion is performed and the file is not modified.",
            file = dst)
    
    print("> giacc.py help", file = dst)
    if verbose > 0:
        print("\tDisplays this usage message.", file = dst)



class FileType(Enum):
    GIP = 1
    GIL = 2
    GIA = 3
    GIR = 4

class AssetMode(Enum):
    BEYOND  = 0
    CLASSIC = 1

HeaderStruct    = struct.Struct(">IIIII")   # uint32_t x5
HeaderTuple = namedtuple("HeaderTuple", ["file_len", "file_ver", "magic_num", "file_type", "content_len"])
FILE_LEN_EXCLUDED   = 4 # File length field does not count itself
MAGIC_NUM_HEAD  = 806   # Expected magic_num value - error if not equal to this

FooterStruct    = struct.Struct(">I")   # uint32_t x1
FooterTuple = namedtuple("FooterTuple", ["magic_num"])
MAGIC_NUM_TAIL  = 1657  # Expected magic_num value - error if not equal to this

CLASSIC_MODE_TAG    = bytes.fromhex("20 01");
FILENAME_TERMINATOR = bytes.fromhex("2A 05");



if __name__ == "__main__":
    
    #----- PARSING CMD ARGS -----#
    
    if len(sys.argv) < 2:
        bad_argv("Missing operation argument")
    
    # Check operation
    match sys.argv[1].casefold():
        case "to-classic":
            to_type = AssetMode.CLASSIC
        case "to-beyond":
            to_type = AssetMode.BEYOND
        case "query":
            to_type = None  # No conversion
        case "help":
            print_help()
            sys.exit()
        case _:
            bad_argv("Unknown or invalid operation \"" + sys.argv[1] + "\"");
    
    # Get input/output filenames
    if to_type != None:
        if len(sys.argv) < 4:
            if len(sys.argv) < 3:
                bad_argv("Missing input/output filename arguments")
            else:
                bad_argv("Missing output filename argument")
        
        src_path    = sys.argv[2]
        dst_path    = sys.argv[3]
        
        if dst_path == "*":
            # Destination is same as source
            dst_path    = None
    else:
        if len(sys.argv) < 3:
            bad_argv("Missing input filename argument")
        
        src_path    = sys.argv[2]
        #dst_path    = None
    
    #----- PARSE INPUT FILE -----#
    
    try:
        
        if to_type != None and dst_path == None:
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
            
            header  = HeaderTuple._make(HeaderStruct.unpack_from(src, 0))
            # Validate header
            if header.file_len != (len(src) - FILE_LEN_EXCLUDED):
                error_file_invalid(src_path)
            if header.magic_num != MAGIC_NUM_HEAD:
                error_file_invalid(src_path)
            if header.file_type != FileType.GIA.value:
                error_file_invalid(src_path)
            if header.content_len != (len(src) - HeaderStruct.size - FooterStruct.size):
                error_file_invalid(src_path)
        
            footer  = FooterTuple._make(FooterStruct.unpack(src[-FooterStruct.size : ]))
            # Validate footer
            if footer.magic_num != MAGIC_NUM_TAIL:
                error_file_invalid(src_path)
            
            # Find index of filename terminator, searching backwards from footer
            fterm_index  = src.rfind(FILENAME_TERMINATOR, 0, -FooterStruct.size)
            if fterm_index < 0:
                error_file_invalid(src_path)
            
            # Expected index of classic mode tag
            ctag_index   = fterm_index - len(CLASSIC_MODE_TAG)
            
            # Check for classic mode tag
            if ctag_index >= HeaderStruct.size and src[ctag_index : fterm_index] == CLASSIC_MODE_TAG:
                from_type   = AssetMode.CLASSIC
            else:
                from_type   = AssetMode.BEYOND
                ctag_index  = fterm_index
            
            print("This asset is", " already" if from_type == to_type else "", " for ", from_type.name.title(), " Mode.", sep = "")
            
            if to_type == None:
                # Only querying asset type, don't do any conversion
                sys.exit()
            
            #----- WRITE OUTPUT FILE -----#
            
            if from_type == to_type:
                print("No changes will be made.")
                
                if dst_path == None:
                    # Destination is same as source - no action needed
                    pass
                
                else:
                    # Copy source to destination unmodified
                    with open(dst_path, "wb") as dst:
                        dst.write(src)
            else:
                print("Converting asset to", to_type.name.title(), "Mode...")
                
                # Correct header length fields
                if to_type == AssetMode.CLASSIC:
                    len_adjustment  = +len(CLASSIC_MODE_TAG)
                elif to_type == AssetMode.BEYOND:
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
                    if to_type == AssetMode.CLASSIC:
                        # Make room for the classic mode tag
                        src.resize(len_old + len_adjustment)    # First grow the file
                        src.move(fterm_index_new, fterm_index, len_old - fterm_index)   # Shift everything after the tag down
                        
                        src[ctag_index : ctag_index + len(CLASSIC_MODE_TAG)] = CLASSIC_MODE_TAG  # and write the tag
                    else:
                        # Delete the classic mode tag
                        src.move(fterm_index_new, fterm_index, len_old - fterm_index)   # Shift everything after the tag up
                        src.resize(len_old + len_adjustment)    # And shrink the file
                    
                    HeaderStruct.pack_into(src, 0, *header_new) # Also rewrite the header
                    
                else:
                    # Copy to destination with classic mode tag added/removed
                    with open(dst_path, "wb") as dst:
                        
                        dst.write(HeaderStruct.pack(*header_new))
                        
                        # Write everything before the classic mode tags
                        dst.write(src[HeaderStruct.size : ctag_index])
                        
                        if to_type == AssetMode.CLASSIC:
                            # Write the classic mode tag
                            dst.write(CLASSIC_MODE_TAG)
                        
                        # Everything else
                        dst.write(src[fterm_index : ])
        
    except OSError as e:
        sys.exit(e)
    else:
        print("Conversion completed.")
        sys.exit()