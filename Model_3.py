import networkx as nx
import numpy as np
import matplotlib.pyplot as plt
import random

# 1. Генерация иерархического мезорынка 
def generate_platform_fixed():
    G = nx.DiGraph()
    root = 0
    G.add_node(root, level=1)
    
    hubs = [1, 2, 3, 4] # 4 хаба 
    for h in hubs:
        G.add_node(h, level=2)
        G.add_edge(root, h)
        
    node_id = 5
    for h in hubs:
        for _ in range(4): # по 4 фирмы на хаб
            eff = random.uniform(0.6, 1.4)
            G.add_node(node_id, level=3, efficiency=eff)
            G.add_edge(h, node_id)
            node_id += 1
    return G

# 2. Экономический расчет
def compute_economics(G, A, r, base_c=10):
    prices, quantities = [], []
    total_money_flow = 0
    
    firms = [n for n in G.nodes if G.nodes[n].get('level') == 3]
    for f in firms:
        eff = G.nodes[f].get('efficiency', 1.0)
        cost = (base_c * 1.2) / eff
        price = cost * (1 + r)
        quantity = max(A - 1.5 * price, 0)
        profit = (price - cost) * quantity
        
        G.nodes[f]['price'] = price
        G.nodes[f]['quantity'] = quantity
        G.nodes[f]['profit'] = profit
        
        prices.append(price)
        quantities.append(quantity)
        total_money_flow += price * quantity
            
    return {
        'avg_price': np.mean(prices) if prices else 0,
        'avg_quantity': np.mean(quantities) if quantities else 0,
        'total_quantity': sum(quantities),
        'total_money_flow': total_money_flow
    }

# 3. Моделирование алгоритма цифровой платформы 
def platform_aggressive_reorg(G):
    hubs = [1, 2, 3, 4]
    # Находим лучший хаб по суммарной прибыли его дочерних фирм 
    hub_perf = {h: sum(G.nodes[f].get('profit', 0) for f in G.successors(h)) for h in hubs}
    best_hub = max(hub_perf, key=hub_perf.get)
    
    firms = [n for n in G.nodes if G.nodes[n].get('level') == 3]
    avg_profit = np.mean([G.nodes[f].get('profit', 0) for f in firms])
    
    # Платформа переводит все фирмы с прибылью ниже средней в лучший хаб
    for f in firms:
        if G.nodes[f].get('profit', 0) < avg_profit:
            old_parent = list(G.predecessors(f))[0]
            if old_parent != best_hub:
                G.remove_edge(old_parent, f)
                G.add_edge(best_hub, f)

# 4. Позиционирование иерархии
def hierarchy_pos(G, root=0, width=1.0, vert_gap=0.3, vert_loc=0, xcenter=0.5):
    pos = {}
    def _hierarchy_pos(node, width, vert_loc, xcenter):
        pos[node] = (xcenter, vert_loc)
        children = list(G.successors(node))
        if children:
            dx = width / max(1, len(children))
            nextx = xcenter - width/2 + dx/2
            for child in children:
                _hierarchy_pos(child, dx, vert_loc - vert_gap, nextx)
                nextx += dx
    _hierarchy_pos(root, width, vert_loc, xcenter)
    return pos

# Запуск модели на 20 шагах 
T = 20
G = generate_platform_fixed()
history = []
A_seq = np.linspace(100, 150, T)
r = 0.12

for t in range(T):
    stats = compute_economics(G, A_seq[t], r)
    stats['t'] = t
    history.append(stats)
    platform_aggressive_reorg(G)

# Визуализация результатов 

# 1. График конечной сети
plt.figure(figsize=(10, 7))
pos = hierarchy_pos(G)
nx.draw_networkx_nodes(G, pos, node_color='#1F1777', node_size=700)
nx.draw_networkx_edges(G, pos, edge_color='#1F1777', alpha=0.4, arrows=True, arrowsize=20)
nx.draw_networkx_labels(G, pos, font_color='white', font_size=9)
plt.title(f"Конечная сеть", fontsize=14)
plt.axis('off')
plt.show()

# 2. Экономические графики
fig, axes = plt.subplots(2, 2, figsize=(14, 9))
t_axis = [h['t'] for h in history]

metrics = [
    ('avg_price', 'Средняя цена'),
    ('avg_quantity', 'Средний объем производства'),
    ('total_money_flow', 'Совокупный денежный поток'),
    ('total_quantity', 'Совокупный объем производства')
]

for i, (key, title) in enumerate(metrics):
    ax = axes[i//2, i%2]
    data = [h[key] for h in history]
    ax.plot(t_axis, data, color='#1F1777', linewidth=2, marker='o', markersize=6, markerfacecolor='#1F1777')
    ax.set_title(title, fontsize=12)
    ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.show()
