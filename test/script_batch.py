from patternmatching.gray import query_call

fname = "./sample/dynamic/test0.json"
qargs = "--vertex a b c --edge x:a:b y:b:c z:c:a --vertexlabel a:cyan b:cyan c:cyan".split(" ")
query_call.run_query(fname, qargs, False, False)

fname = "./sample/dynamic/test1.json"
qargs = "--vertex a b c --edge x:a:b y:b:c z:c:a --vertexlabel a:cyan b:cyan c:cyan".split(" ")
query_call.run_query(fname, qargs, False, False)


fname = "./data/Congress1.json"
qargs = "--vertex a b c --edge x:a:b y:b:c z:c:a --vertexlabel a:cyan b:cyan c:cyan".split(" ")
query_call.run_query(fname, qargs, False, False)