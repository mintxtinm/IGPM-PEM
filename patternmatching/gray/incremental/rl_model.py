import networkx as nx
import community
import gym

import gray_incremental

gym.envs.register(id='graphenv-v0', entry_point='GraphEnv')


def recursive_louvain(graph, min_size):
  def get_louvain(g):
    partition = community.best_partition(g)
    return partition

  def create_reverse_partition(pt):
    rev_part = dict()
    for k in pt:
      v = pt[k]
      if not v in rev_part:
        rev_part[v] = list()
      rev_part[v].append(k)
    return rev_part
  
  def __inner_recursive_louvain(g, num_th):
    _, pt = get_louvain(g)
    rev_part = create_reverse_partition(pt)
    mem_list = list()
    
    if len(rev_part) == 1:
      return [rev_part[0]]
    
    for members in rev_part.values():
      cluster = g.subgraph(members)
      if len(members) >= num_th:
        small_members_list = __inner_recursive_louvain(cluster, num_th)
        mem_list.extend(small_members_list)
      else:
        mem_list.append(members)
    
    return mem_list

  members_list = __inner_recursive_louvain(graph, min_size)
  num_groups = len(members_list)
  part = dict()
  for gid in range(num_groups):
    for member in members_list[gid]:
      part[member] = gid

  return part, create_reverse_partition(part)
  

def get_recompute_nodes(graph, affected, min_size):
  part, rev_part = recursive_louvain(graph, min_size)
  nodes = set()
  
  for n in affected:
    if not n in part:
      continue
    gid = part[n]
    mem = set(rev_part[gid])
    nodes.update(mem)
    
  return nodes



class GraphEnv(gym.Env):
  """Reinforcement learning environment for graph object

  """
  
  def __init__(self, graph, query, cond, max_step):
    """Constructor of an environment object for graph
    
    :param graph: Input data graph
    :param query: Query data graph
    :param cond: Condition object
    :param max_step: Number of iterations
    """
    super(gym.Env, self).__init__()
    self.action_space = [-1, +1]
    self.observation_space = gym.spaces.Discrete(2)  # Number of nodes, edges
    self.max_reward = 100.0
    self.reward_range = [-1., self.max_reward]
    self.grm = gray_incremental.GRayIncremental(graph, query, graph.is_directed(), cond)
    self.max_step = max_step
    self.step = 0
    self.node_threshold = 10
    self.min_threshold = 4
    self.reset()

    ## Extract edge timestamp
    add_edge_timestamps = nx.get_edge_attributes(graph, "add")  # edge, time
    def dictinvert(d):
      inv = {}
      for k, v in d.iteritems():
        keys = inv.setdefault(v, [])
        keys.append(k)
      return inv
    self.add_timestamp_edges = dictinvert(add_edge_timestamps)  # time, edges
    
    
  
  def step(self, action):
    
    if action == -1 and self.node_threshold > self.min_threshold:
      self.node_threshold -= 1
    elif action == +1:
      self.node_threshold += 1
    
    t = self.step
    add_edges = self.add_timestamp_edges[t]
    nodes = set([src for (src, dst) in add_edges] + [dst for (src, dst) in add_edges])
    affected_nodes = get_recompute_nodes(self.grm.graph, nodes, self.node_threshold)
    self.grm.run_incremental_gray(add_edges, affected_nodes)
    self.step += 1
    
    return self.grm.get_observation(), self.grm.get_reward(self.max_reward), self.step >= self.max_step, {}
    
  
  def reset(self):
    return self.observation_space
  
  
  def render(self, mode='human', close=False):
    print self.step, self.observation_space, self.node_threshold
  
  def close(self):
    pass
  
  def seed(self, seed=None):
    pass
  

