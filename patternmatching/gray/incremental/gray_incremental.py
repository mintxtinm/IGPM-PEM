"""
Extract multiple pattern subgraphs with G-Ray algorithm

Tong, Hanghang, et al. "Fast best-effort pattern matching in large attributed graphs."
Proceedings of the 13th ACM SIGKDD international conference on Knowledge discovery and data mining. ACM, 2007.
"""

import networkx as nx

from patternmatching.gray import extract, rwr
from patternmatching.gray.incremental import extract_incremental
from patternmatching.gray.gray_multiple import GRayMultiple
from patternmatching.gray.incremental.partial_execution_manager import PEM
from patternmatching.query.Condition import *
from patternmatching.query import QueryResult


def equal_graphs(g1, g2):
  ns1 = set(g1.nodes())
  ns2 = set(g2.nodes())
  # logging.debug("Node 1: " + str(ns1))
  # logging.debug("Node 2: " + str(ns2))
  diff = ns1 ^ ns2
  if diff:  ## Not empty (has differences)
    return False
  
  es1 = set(g1.edges())
  es2 = set(g2.edges())
  # logging.debug("Edge 1: " + str(es1))
  # logging.debug("Edge 2: " + str(es2))
  diff = es1 ^ es2
  if diff:
    return False
  
  return True


def valid_result(result, query, nodemap):
  ## TODO: The number of vertices and edges of graphs with paths will vary
  hasPath = False
  etypes = nx.get_edge_attributes(query, TYPE)
  for k, v in etypes.iteritems():
    if v == PATH:
      hasPath = True
      break
  
  if not hasPath:
    nr_num = result.number_of_nodes()
    nq_num = query.number_of_nodes()
    if nr_num != nq_num:
      return False
    
    er_num = result.number_of_edges()
    eq_num = query.number_of_edges()
    if er_num != eq_num:
      return False

  # print nodemap
  # print query.edges()
  # print result.edges()
  for qn, rn in nodemap.iteritems():
    qd = query.degree(qn)
    rd = result.degree(rn)
    # print "degree:", qn, qd, rn, rd
    if qd != rd:
      return False
  
  return True


class GRayIncremental(object, GRayMultiple):
  def __init__(self, graph, query, directed, cond):
    super(GRayIncremental, self).__init__(graph, query, directed, cond)
    self.pem = PEM(graph)
  
  def update_graph(self, nodes, edges):
    self.graph.add_nodes(nodes)
    self.graph.add_edges(edges)
  
  
  def run_gray(self):
    """
    Run batch G-Ray algorithm
    :return:
    """
    logging.info("---- Start Batch G-Ray ----")
    logging.info("#### Compute RWR")
    self.computeRWR()
    logging.info("#### Compute Extract")
    ext = extract.Extract(self.graph, self.graph_rwr)
    ext.computeExtract()
    self.extracts[''] = ext

    logging.debug("#### Find Seeds")
    k = list(self.query.nodes())[0]
    kl = Condition.get_node_label(self.query, k)
    kp = Condition.get_node_props(self.query, k)
    seeds = Condition.filter_nodes(self.graph, kl, kp)  # Find all candidates
    # seeds = [s for s in self.graph.nodes() if self.get_node_label(self.graph, s) == kl]  # Find all candidates
    if not seeds:  ## No seed candidates
      logging.debug("No more seed vertices available. Exit G-Ray algorithm.")
      return
    
    for i in seeds:
      logging.debug("#### Choose Seed: " + str(i))
      result = nx.MultiDiGraph() if self.directed else nx.MultiGraph()
      # self.results.append(result)
      
      touched = []
      nodemap = {}  ## Query Vertex -> Graph Vertex
      unprocessed = self.query.copy()
      # unprocessed = nx.MultiDiGraph(self.query) if self.directed else nx.MultiGraph(self.query)
      
      il = Condition.get_node_label(self.graph, i)
      props = Condition.get_node_props(self.graph, i)
      nodemap[k] = i
      # result.add_node(i, label=il)
      result.add_node(i)
      result.nodes[i][LABEL] = il
      for name, value in props.iteritems():
        result.nodes[i][name] = value
      
      # logging.debug("## Mapping node: " + str(k) + " : " + str(i))
      touched.append(k)
      
      self.process_neighbors(result, touched, nodemap, unprocessed)
  
  
  def run_incremental_gray(self, nodes):
    """
    Run incremental G-Ray algorithm
    :param nodes:
    :return:
    """
    logging.info("---- Start Incremental G-Ray ----")
    logging.info("#### Compute RWR")
    self.compute_part_RWR(nodes)
    logging.info("#### Compute Extract")
    ext = extract_incremental.Extract(self.graph, self.graph_rwr)
    ext.computeExtract_incremental(nodes)
    
  
  def getExtract(self, label):
    if not label in self.extracts:
      ext = extract.Extract(self.graph, self.graph_rwr, label)
      ext.computeExtract()
      self.extracts[label] = ext
    return self.extracts[label]

  def append_results(self, result, nodemap):
    if self.cond is not None and not self.cond.eval(result, nodemap):
      return False  ## Not satisfied with complex condition
    
    for r in self.results:
      rg = r.get_graph()
      if equal_graphs(rg, result):
        return False
    qresult = QueryResult.QueryResult(result, nodemap)
    self.results.append(qresult)
    return True

  
  def process_neighbors(self, result, touched, nodemap, unproc):
    if unproc.number_of_edges() == 0:
      if valid_result(result, self.query, nodemap):
        logging.debug("###### Found pattern " + str(self.count))
        if self.append_results(result, nodemap):
          self.count += 1
        return
      else:
        logging.debug("No more edges available. Exit G-Ray algorithm.")
        return
    
    k = None
    l = None
    kl = None
    reversed_edge = False
    for k_ in touched:
      kl = Condition.get_node_label(self.query, k_)
      kp = Condition.get_node_props(self.query, k_)
      
      ## Forward Edge
      for l_ in self.query.neighbors(k_):
        # print k_, kl, kp, l_, unproc.edges()
        if not unproc.has_edge(k_, l_):
          continue
        l = l_
        break
      if l is not None:
        k = k_
        # logging.debug("#### Process neighbors " + str(k) + " -> " + str(l))
        break
      
      ## Reversed Edge
      if self.directed:
        for l_ in self.query.predecessors(k_):
          if not unproc.has_edge(l_, k_):
            continue
          l = l_
          break
        if l is not None:
          reversed_edge = True
          k = k_
          # logging.debug("#### Process neighbors " + str(k) + " <- " + str(l))
          break
          
    
    if l is None:
      logging.debug("No more vertices with the same label available. Exit G-Ray algorithm.")
      return
    
    logging.debug("#### Start Processing Neighbors from " + str(k) + " count " + str(self.count))
    logging.debug("## result: " + " ".join([str(e) for e in result.edges()]))
    logging.debug("## touchd: " + " ".join([str(n) for n in touched]))
    logging.debug("## nodemp: " + str(nodemap))
    logging.debug("## unproc: " + " ".join([str(e) for e in unproc.edges()]))
    
    i = nodemap[k]
    touched.append(l)
    ll = Condition.get_node_label(self.query, l)
    lp = Condition.get_node_props(self.query, l)
    logging.debug("## Find the next vertex " + str(k) + "[" + kl + "] -> " + str(l) + "[" + ll + "]")
    
    is_path = False
    if not reversed_edge and Condition.is_path(self.query, k, l) or reversed_edge and Condition.is_path(self.query, l, k):
      is_path = True
    
    #### Find a path or edge (Begin)
    src, dst = (l, k) if reversed_edge else (k, l)
    
    elabel = Condition.get_edge_label(unproc, src, dst)
    # print elabel
    if elabel is None:  # Any label is OK
      eid = None
      el = ''
    else:
      eid = elabel[0]
      el = elabel[1]
    Condition.remove_edge_from_id(unproc, src, dst, eid)
    
    
    if is_path:
      paths = self.getExtract(el).getPaths(i)
      if not paths:
        logging.debug("No more paths available. Exit G-Ray algorithm.")
        return
      for j, path in paths.iteritems():
        result_ = nx.MultiDiGraph(result) if self.directed else nx.MultiGraph(result)
        touched_ = list(touched)
        nodemap_ = dict(nodemap)
        unproc_ = nx.MultiDiGraph(unproc) if self.directed else nx.MultiGraph(unproc)
    
        if l in nodemap_ and nodemap_[l] != j:
          prevj = nodemap_[l]
          result_.remove_node(prevj)
    
        nodemap_[l] = j
        props = Condition.get_node_props(self.graph, j)
        result_.add_node(j)
        for key, value in props.iteritems():
          result_.nodes[j][key] = value
        
        prev = i
        for n in path:
          result_.add_edge(prev, n)
          prev = n
        self.process_neighbors(result_, touched_, nodemap_, unproc_)
    
    else:
      if l in nodemap:
        jlist = [nodemap[l]]
      else:
        jlist = self.neighbor_expander(i, k, l, result, reversed_edge)  # find j(l) from i(k)
        if not jlist:  ## No more neighbor candidates
          logging.debug("No more neighbor vertices available. Exit G-Ray algorithm.")
          return
      
      for j in jlist:
        g_src, g_dst = (j, i) if reversed_edge else (i, j)
        if g_src == g_dst:  ## No bridge process necessary
          continue
        path = self.bridge(g_src, g_dst)
        # if len(path) != 1:
        if not path:
          logging.debug("## No path found: " + str(g_src) + " -> " + str(g_dst))
          continue
        logging.debug("## Find path from " + str(g_src) + " -> " + str(g_dst) + ": " + " ".join(str(n) for n in path))
        
        result_ = nx.MultiDiGraph(result) if self.directed else nx.MultiGraph(result)
        touched_ = list(touched)
        nodemap_ = dict(nodemap)
        unproc_ = nx.MultiDiGraph(unproc) if self.directed else nx.MultiGraph(unproc)
    
        if l in nodemap_ and nodemap_[l] != j:  ## Need to replace mapping
          prevj = nodemap_[l]
          result_.remove_node(prevj)
        nodemap_[l] = j
        props = Condition.get_node_props(self.graph, j)
        result_.add_node(j)
        # print props
        for k, v in props.iteritems():
          result_.nodes[j][k] = v
        # print result_.nodes(data=True)[j]
        
        prev = g_src
        valid = True
        for n in path:
          # print path, prev, n
          if not Condition.has_edge_label(self.graph, prev, n, el):
            valid = False
            break
          result_.add_edge(prev, n)
          prev = n
        if valid:
          self.process_neighbors(result_, touched_, nodemap_, unproc_)
    #### Find a path or edge (End)
    
  def compute_part_RWR(self, nodes):
    RESTART_PROB = 0.7
    OG_PROB = 0.1
    rw = rwr.RWR(self.graph)
    for m in nodes:
      results = rw.run_exp(m, RESTART_PROB, OG_PROB)
      self.graph_rwr[m] = results
  
  def getRWR(self, m, n):
    return self.graph_rwr[m][n]
  
  #def getExtract(self):
  #  return self.extract
  
  @staticmethod
  def rwr(g, m, n):  # Random walk with restart m -> n in g
    RESTART_PROB = 0.7
    OG_PROB = 0.1
    rw = rwr.RWR(g)
    results = rw.run_exp(m, RESTART_PROB, OG_PROB)
    logging.debug("RWR: " + str(m) + " -> " + str(n) + " " + str(results))
    return results[n]



