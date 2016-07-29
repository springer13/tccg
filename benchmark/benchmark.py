import os
import random
import copy
import ctf
import argparse

_tensorToolboxRoot = "PATH_TO/tensor_toolbox" #set this if tensor_toolbox is available
_CTFRoot = "PATH_TO/CTF"
_tensorSize = 200. * 2**20 # Size of the largest tensor in bytes
_dimensionMultipleStride1 = 24 # each stride-1 dimension has to be a multiple of this value
_dimensionMultiple = 4 
_fullbenchmark = 0

_columnMajor = 1
#########################################
# Do not change setting below this line
#########################################

# these test cases are taken from "Using Machine Learning to Improve Automatic Vectorization" by Stock et al.
if( _fullbenchmark ):
   testcases_ccsd =[   
    "ij-ik-kj",
    "ij-ikl-ljk",
    "ij-kil-lkj",
    "ijk-ikl-lj",
    "ijk-il-jlk",
    "ijk-ilk-jl",
    "ijk-ilk-lj",
    "ijk-ilmk-mjl",
    "ijkl-imjn-lnkm",
    "ijkl-imjn-nlmk",
    "ijkl-imkn-jnlm",
    "ijkl-imkn-njml",
    "ijkl-imln-jnkm",
    "ijkl-imln-njmk",
    "ijkl-imnj-nlkm",
    "ijkl-imnk-njml",
    "ijkl-minj-nlmk",
    "ijkl-mink-jnlm",
    "ijkl-minl-njmk" ]
else:
   testcases_ccsd =[   
    "ij-ik-kj",
    "ij-ikl-ljk",
    "ij-kil-lkj",
    "ijk-ikl-lj",
    "ijk-ilk-jl",
    "ijk-ilmk-mjl",
    "ijkl-imjn-lnkm",
    "ijkl-imjn-nlmk",
    "ijkl-minl-njmk" ]
# these test cases are taken from "Synthesis of High-Performance Parallel Programs for a Class of Ab Initio Quantum Chemistry Models"
testcases_ao2mo = [
            "aqrs-pa-pqrs", 
            "abrs-qb-aqrs", 
            "abcs-rc-abrs"] 

# these test cases are similar to those used in "An Input-Adaptive and In-Place Approach to Dense Tensor-Times-Matrix Multiply"
testcases_intensli = [
            "abj-bka-kj",
            "ajb-kba-jk",
            "abjc-cbka-kj",
            "ajbc-ckba-jk",
            "abjc-kbac-jk",
            "abjcd-dkbac-jk",
            "adbjc-cbdka-kj",
            "ajbdc-ckbad-jk"]
 
# these test cases are taken from "Efficient Implementation of Many-body Quantum Chemical Methods on the Intel Xeon Phi Coprocessor"
if( _fullbenchmark ):
   testcases_ccsd_t = [
    "abcijk-ijma-mkbc",
    "abcijk-ijmb-mkac",
    "abcijk-ijmc-mkab",
    "abcijk-ikma-mjbc",
    "abcijk-ikmb-mjac",
    "abcijk-ikmc-mjab",
    "abcijk-jkma-mibc",
    "abcijk-jkmb-miac",
    "abcijk-jkmc-miab",
    "abcijk-eiab-jkec",
    "abcijk-eiac-jkeb",
    "abcijk-eibc-jkea",
    "abcijk-ejab-ikec",
    "abcijk-ejac-ikeb",
    "abcijk-ejbc-ikea",
    "abcijk-ekab-ijec",
    "abcijk-ekac-ijeb",
    "abcijk-ekbc-ijea"
                  ]
else:
   testcases_ccsd_t = [
    "abcijk-ijma-mkbc",
    "abcijk-ijmb-mkac",
    "abcijk-ijmc-mkab",
    "abcijk-ikmb-mjac"
                  ]

testcases_transC = [
    "abc-bk-akc"
    ]

_sortedTCs = [  # TCs are sorted w.r.t. single-precision GEMM performance on a single Haswell core (i.e., first entry is bandwidth-bound while the last entry is compute bound)
        "abcde-efbad-cf",
        "abcde-efcad-bf",
        "abcd-dbea-ec",
        "abcde-ecbfa-fd",
        "abcd-deca-be",
        "abc-bda-dc",
        "abcd-ebad-ce",
        "abcdef-dega-gfbc",
        "abcdef-dfgb-geac",
        "abcdef-degb-gfac",
        "abcdef-degc-gfab",
        "abc-dca-bd",
        "abcd-ea-ebcd",
        "abcd-eb-aecd",
        "abcd-ec-abed",
        "abc-adec-ebd",
        "ab-cad-dcb",
        "ab-acd-dbc",
        "abc-acd-db",
        "abc-adc-bd",
        "ab-ac-cb",
        "abcd-aebf-fdec",
        "abcd-eafd-fbec",
        "abcd-aebf-dfce"
        ]

def normalize(tc): #normalize labels
    C = tc.split('-')[0]
    A = tc.split('-')[1]
    B = tc.split('-')[2]

    currentChar = 'A'
    for i in range(len(C)):
        posA = A.find(C[i])
        if( posA != -1 ):
            A = A.replace(A[posA], currentChar)
        posB = B.find(C[i])
        if( posB != -1 ):
            B= B.replace(B[posB], currentChar)
        C = C.replace(C[i], currentChar)
        currentChar = chr(ord(currentChar)+1)

    for i in range(len(A)):
        if( C.find(A[i]) == -1 ): # only contracted
            posB = B.find(A[i])
            if( posB != -1 ):
                B = B.replace(B[posB], currentChar)
            A = A.replace(A[i], currentChar)
            currentChar = chr(ord(currentChar)+1)
    tc_ = C + "-"+A + "-"+B
    tc_ = tc_.lower()
    return tc_

def getDataTypeSize(dataType):
   if(dataType == 's'):
      return 4
   elif(dataType == 'd'):
      return 8

def createTensor( encoding, label ):
   T = "%s["%label
   for c in encoding:
      T += "%c, "%c
   T = T[:-2] + "]"
   return T

def print_gett(A, B, C, sizes, filename, stdout):
       f = open(filename, "w")
       f.write("%s = %s * %s\n"%(C, A, B))
       sizeStr = ""
       for idx in sizes:
          sizeStr += "%s:%d;"%(idx, sizes[idx])
          f.write("%s = %d\n"%(idx, sizes[idx]))
       cstr = ""
       C = C[2:-1].split(',')
       for c in C:
           cstr += c.strip()
       cstr += "-"
       A = A[2:-1].split(',')
       for c in A:
           cstr += c.strip()
       cstr += "-"
       B = B[2:-1].split(',')
       for c in B:
           cstr += c.strip()
       stdout.append("%s & %s"%(cstr,sizeStr))
       f.close()

def print_ctf(code, filename):
       f = open(filename, "w")
       f.write(code)
       f.close()

def print_matlab(size,astr,bstr,cstr, dataType, f):
    asize = ""
    contrA = ""
    contrB = ""
    cstr_tt = "" #tensor toolbox arranges the indices from A followed by the indices of B
    for c in astr:
        if( bstr.find(c) != -1 ): #contracted indice
           contrA += "%d,"%(astr.find(c)+1)
           contrB += "%d,"%(bstr.find(c)+1)
        else: #free indice
            cstr_tt += c
        asize += "%d,"%size[c]
    asize = asize[:-1]
    bsize = ""
    for c in bstr:
        if( astr.find(c) == -1 ): #free indice
            cstr_tt += c
        bsize += "%d,"%size[c]
    bsize = bsize[:-1]
    contrA = contrA[:-1]
    contrB = contrB[:-1]
    csize = ""
    csizeTotal = 1
    for c in cstr:
         csize += "%d,"%size[c]
         csizeTotal *= size[c]
    csize = csize[:-1]
    flops = 2.0
    for c in size:
       flops *= size[c]
 
    if( dataType == "s" ):
        f.write("Tensor Toolbox doesn't support single-precision\n")
        return
    f.write("A = rand(%s);\n"%asize)
    f.write("B = rand(%s);\n"%bsize)
    f.write("AT = tensor(A); %% %s\n"%astr)
    f.write("BT = tensor(B); %% %s\n"%bstr)
    f.write("tic\n")
    f.write("CT = ttt(AT,BT,[%s],[%s]); %% %s\n"%(contrA,contrB,cstr_tt + " = "+astr+" "+bstr))
    if( cstr != cstr_tt):
        permC = ""
        for c in cstr:
           permC += "%d,"%(cstr_tt.find(c)+1)
        f.write("C = permute(CT,[%s]); %% %s\n"%(permC[:-1],cstr + " <- "+cstr_tt))
    f.write("t = toc;\n")
    f.write("gflops = %e;\n"%(flops/1e9))
    f.write("fprintf('%s-%s-%s %%f\\n',gflops/t)\n\n"%(cstr,astr,bstr))

def generate(testcases,benchmarkName,arch,numThreads,maxImplementations,floatType,matlabfile, stdout, sizes = {}):
    ctf_sh = open("ctf_"+benchmarkName+".sh","w")
    ctf_sh.write("CTF_ROOT=%s\n"%_CTFRoot)
    gett = open("gett_"+benchmarkName+".sh","w")

    gett.write("rm -f gett_tmp.dat\n") #remove old dat files
    ctf_sh.write("rm -f ctf_tmp.dat\n") #remove old dat files

    counter = 0
    for test in testcases:
       #print test,normalize(test) 
       test_normalized = normalize(test)
       sizes_normalized = {}
       for c in sizes:
           pos = test.find(c)
           #print pos
           sizes_normalized[test_normalized[pos]] = sizes[c]
       test = test_normalized
       sizesTmp = copy.deepcopy(sizes_normalized)
       tensors = test.split("-")
       if( not _columnMajor ):
          for i in range(len(tensors)):
             tensors[i] = tensors[i][::-1]

       # define tensors
       A = createTensor(tensors[1], "A")
       B = createTensor(tensors[2], "B")
       C = createTensor(tensors[0], "C")

       # the tensor with the largest dimension determines the size of each index
       maxDim = len(tensors[1])
       maxDim = max(maxDim ,len(tensors[2]))
       maxDim = max(maxDim , len(tensors[0]))
       
       # make all indices roughly equal in size
       averageIndexSize = pow(_tensorSize / getDataTypeSize(floatType), 1./maxDim)

       # determine size
       indices = []
       for c in test:
          if( c != "-" ):
              indices.append(c)
       indices = set(indices)
       for idx in indices:
          if( not sizesTmp.has_key(idx) ):
              if( idx == tensors[0][0] or idx == tensors[1][0] or idx == tensors[2][0] ):
                  # each stride-1 index should be a multiple of _dimensionMultiple 
                  sizesTmp[idx] = int((averageIndexSize + _dimensionMultipleStride1 - 1) / _dimensionMultipleStride1) * _dimensionMultipleStride1
              else:
                  sizesTmp[idx] = averageIndexSize
                  avgUP = int((averageIndexSize + _dimensionMultiple - 1) / _dimensionMultiple) * _dimensionMultiple
                  avgFloor = max(_dimensionMultiple, int((averageIndexSize) / _dimensionMultiple) * _dimensionMultiple)
                  if( abs(averageIndexSize - avgUP) < abs(averageIndexSize - avgFloor) ): #pick closest match
                      sizesTmp[idx] = avgUP
                  else:
                      sizesTmp[idx] = avgFloor

       #sizeStr = ""
       #for s in sizesTmp:
       #    sizeStr += "%s:%d;"%(s,sizesTmp[s])
       #print "lookupSizes[\"%s-%s-%s\"] = \"%s\""%(tensors[0],tensors[1],tensors[2],sizeStr)

       print_gett(A,B,C,sizesTmp,benchmarkName+"%d"%counter + ".tccg", stdout)
       gett.write("echo \""+test+"\" | tee >> gett_tmp.dat\n")
       gett.write("tccg --testing --maxImplementations=%d --arch=%s --floatType=%s --numThreads=%d "%(maxImplementations, arch, floatType, numThreads)+benchmarkName+"%d"%counter + ".tccg | tee > %s%d.dat\n"%(benchmarkName,counter))
       gett.write("cat "+"%s%d.dat"%(benchmarkName,counter) + " | grep \"Best Loop\" >> gett_tmp.dat\n")

       ctfFilename = benchmarkName+"CTF"+"%d"%counter + ".cpp"
       print_matlab(sizesTmp, tensors[1], tensors[2], tensors[0], floatType, matlabfile)
       print_ctf(ctf.genCTF(sizesTmp, tensors[1], tensors[2], tensors[0], floatType), ctfFilename)
       ctf_sh.write("icpc %s -O0 -I${MPI_INCLUDE} -I${CTF_ROOT}/include ${CTF_ROOT}/lib/libctf.a -std=c++0x -L${MPI_LIBDIR} -mkl -lmpi -xHost\n"%(ctfFilename)) #O0 is used to avoid that the compiler removes trashCache()
       ctf_sh.write("echo \""+test+"\" | tee >> ctf_tmp.dat\n")
       ctf_sh.write("KMP_AFFINITY=compact,1 OMP_NUM_THREADS=1  mpirun -np 1 -genv I_MPI_FABRICS shm ./a.out | grep GF >> ctf_tmp.dat\n")
       counter += 1

    gett.write("cat gett_tmp.dat | sed '$!N;s/\\n/ /' > gett_"+benchmarkName+".dat\n") #
    ctf_sh.write("cat ctf_tmp.dat | sed '$!N;s/\\n/ /' > ctf_"+benchmarkName+".dat\n") #

def main():
   parser = argparse.ArgumentParser(description='Generate high-performance C++ code for a given tensor contraction.')
   parser.add_argument('--numThreads', type=int, help='number of threads.')
   parser.add_argument('--maxImplementations', type=int, help='limits the number of GETT candidates (default: 16).')
   parser.add_argument('--arch', metavar='arch', type=str, help='architecture can be either avx2 (default) or avx512.')
   parser.add_argument('--floatType', metavar='floatType', type=str, help='floatType can bei either \'s\' or \'d\'.')
 
   args = parser.parse_args()

   numThreads = 1
   maxImplementations = 16
   arch = "avx2"
   floatType = "s"
   if( args.arch ):
       arch = args.arch
   if( args.numThreads ):
       numThreads = args.numThreads
   if( args.maxImplementations != None):
       maxImplementations = args.maxImplementations
   if( args.floatType != None):
       floatType = args.floatType

   matlabfile = open("tensorToolbox.m","w")
   #init tensor toolbox
   matlabfile.write("maxNumCompThreads(1);\n")
   matlabfile.write("cd %s\n"%_tensorToolboxRoot )
   matlabfile.write("addpath(pwd)\n")
   matlabfile.write("cd met\n")
   matlabfile.write("addpath(pwd)\n")
   matlabfile.write("cd %s\n"%os.getcwd())

   stdout = []
   #print "#ccsd:"
   generate(testcases_ccsd,"ccsd", arch,numThreads,maxImplementations,floatType,matlabfile, stdout )
   #print "#intensli:"
   sizes = {}
   sizes["j"] = 24
   generate(testcases_intensli,"intensli", arch,numThreads,maxImplementations,floatType,matlabfile, stdout , sizes)
   #print "#ao2mo:"
   generate(testcases_ao2mo,"ao2mo", arch,numThreads,maxImplementations,floatType,matlabfile, stdout )
   #print "#ccsd_t:"
   generate(testcases_ccsd_t,"ccsd_t", arch,numThreads,maxImplementations,floatType,matlabfile, stdout )
   matlabfile.close()

   for tc in _sortedTCs:
       for generatedTC in stdout:
           if( generatedTC.startswith(tc) ):
               print generatedTC
               break;

if __name__ == "__main__":
   main()

   
