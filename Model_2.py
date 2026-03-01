import networkx as nx
import numpy as np
import matplotlib.pyplot as plt
import random
from collections import defaultdict
from matplotlib.patches import Patch

# 1. Генерация иерархического мезорынка 
def generate_mesomarket(level2_size=4, level3_size=4):
    G = nx.DiGraph()
    node_id = 0
    # Уровень 1
    G.add_node(node_id, level=1)
    root = node_id
    node_id += 1

    # Уровень 2
    level2_nodes = []
    for _ in range(level2_size):
        G.add_node(node_id, level=2)
        G.add_edge(root, node_id)
        level2_nodes.append(node_id)
        node_id += 1

    # Уровень 3: равномерно распределеяем фирмы между всеми узлами уровня 2
    level3_nodes = []
    total_firms = level2_size * level3_size
    for i in range(total_firms):
        n2 = level2_nodes[i % level2_size]
        G.add_node(node_id, level=3)
        G.add_edge(n2, node_id)
        level3_nodes.append(node_id)
        node_id += 1

    return G

# 2. Расчет издержек и цен
def assign_costs(G, c=10, cost_noise=0.08):
    for node in G.nodes:
        level = G.nodes[node]['level']
        cost = c*(1+0.2*(level-1))
        if cost_noise>0:
            cost *= (1+cost_noise*(random.random()-0.5))
        G.nodes[node]['cost'] = cost

def compute_prices(G, r):
    for node in G.nodes:
        cost = G.nodes[node].get('cost',10)
        G.nodes[node]['price'] = (1+r)*cost

# 3. Расчет спроса и объемов производства
def demand_function(price,A,B=1):
    return max(A-B*price,0)

def compute_production_volumes(G,A,B=1):
    for node in G.nodes:
        price = G.nodes[node].get('price',10)
        G.nodes[node]['quantity'] = demand_function(price,A,B)

# 4. Модель потоков товаров и денег
def compute_flows(G):
    for edge in G.edges:
        G.edges[edge]['goods_flow'] = 0
        G.edges[edge]['money_flow'] = 0
    try:
        topo_order = list(nx.topological_sort(G))
    except nx.NetworkXError:
        topo_order = sorted(G.nodes,key=lambda n:G.nodes[n]['level'])
    for node in topo_order:
        q = G.nodes[node].get('quantity',0)
        succ = list(G.successors(node))
        if succ:
            flow = q/len(succ)
            for s in succ:
                G.edges[(node,s)]['goods_flow'] = flow
                G.edges[(node,s)]['money_flow'] = flow*G.nodes[s].get('price',10)

# 5. Вход и выход фирм
def compute_profits(G):
    for node in G.nodes:
        price = G.nodes[node].get('price',10)
        cost = G.nodes[node].get('cost',10)
        quantity = G.nodes[node].get('quantity',0)
        G.nodes[node]['profit'] = (price-cost)*quantity

def firm_exit(G):
    # Выход фирм — если прибыль отрицательная
    to_remove = []
    for node in list(G.nodes):
        if G.nodes[node].get('level') != 3:
            continue
        profit = G.nodes[node].get('profit', 0)
        if profit < 0:
            to_remove.append(node)
    for n in to_remove:
        if n in G.nodes:
            G.remove_node(n)
    return len(to_remove)

def firm_entry(G, max_node_id, target_level2_size=4, target_level3_size=4):
    current_level2 = [n for n in G.nodes if G.nodes[n]['level']==2]
    root = [n for n in G.nodes if G.nodes[n]['level']==1][0]
    added = 0
    while len(current_level2)<target_level2_size:
        G.add_node(max_node_id,level=2)
        G.add_edge(root,max_node_id)
        current_level2.append(max_node_id)
        max_node_id +=1
        added +=1

    for n2 in current_level2:
        children = [c for c in G.successors(n2) if G.nodes[c].get('level')==3]
        if len(children) == 0:
            G.add_node(max_node_id, level=3)
            G.add_edge(n2, max_node_id)
            max_node_id += 1
            added += 1
    return max_node_id, added

def rewire_connections(G):
    rewired = 0
    for node in G.nodes:
        if G.nodes[node]['level'] in [2,3]:
            preds = list(G.predecessors(node))
            if preds:
                old = preds[0]
                if G.nodes[node]['level'] == 3:
                    old_children_lvl3 = [c for c in G.successors(old) if G.nodes[c].get('level')==3]
                    if len(old_children_lvl3) <= 1:
                        continue
                candidates = [n for n in G.nodes if G.nodes[n].get('level')==G.nodes[node]['level']-1 and n!=old]
                if candidates:
                    new = min(candidates,key=lambda x:G.nodes[x].get('price',10))
                    if G.nodes[new].get('price',10)<G.nodes[old].get('price',10):
                        G.remove_edge(old,node)
                        G.add_edge(new,node)
                        rewired +=1
    return rewired


# Проверяем, что у каждого узла 2-го уровня есть хотя бы один дочерний узел 3-го уровня. Если нет, добавляем его
def ensure_level2_has_child(G, max_node_id):
    added = 0
    level2_nodes = [n for n in G.nodes if G.nodes[n].get('level')==2]
    for n2 in level2_nodes:
        children_lvl3 = [c for c in G.successors(n2) if G.nodes[c].get('level')==3]
        if len(children_lvl3) == 0:
            G.add_node(max_node_id, level=3)
            G.add_edge(n2, max_node_id)
            max_node_id += 1
            added += 1
    return max_node_id, added


# Вход фирм - при росте спроса (добавляем новую фирму к тому узлу 2-го уровня, где меньше всего дочерних фирм 3-го уровня)
def add_firms_on_demand(G, max_node_id, n_new=1, per_level2_limit=1):
    added = 0
    for _ in range(n_new):
        # Считаем число дочерних фирм у каждого узла уровня 2
        level2_nodes = [n for n in G.nodes if G.nodes[n].get('level')==2]
        children_counts = [(n2, len([c for c in G.successors(n2) if G.nodes[c].get('level')==3])) for n2 in level2_nodes]
        # Выбираем узлы с минимальным числом дочерних фирм
        min_count = min(c for n2, c in children_counts)
        candidates = [n2 for n2, c in children_counts if c == min_count and c < per_level2_limit]
        if not candidates:
            break
        # Добавляем новую фирму 
        n2 = random.choice(candidates)
        G.add_node(max_node_id, level=3)
        G.add_edge(n2, max_node_id)
        max_node_id += 1
        added += 1
    return max_node_id, added

# Проверяем, что сеть имеет один корневой узел, и у каждого узла 2-го уровня есть хотя бы один дочерний узел 3-го уровня
def enforce_hierarchy(G, max_node_id, target_level2_size=4, target_level3_size=1):
    added = 0
    # Проверяем корневой узел
    roots = [n for n in G.nodes if G.nodes[n].get('level')==1]
    if not roots:
        G.add_node(max_node_id, level=1)
        root = max_node_id
        max_node_id += 1
        added += 1
    else:
        root = roots[0]
        for extra in roots[1:]:
            if extra in G.nodes:
                G.nodes[extra]['level'] = 2
                if not G.has_edge(root, extra):
                    G.add_edge(root, extra)

    # Проверяем узлы 2-го уровня 
    level2_nodes = [n for n in G.nodes if G.nodes[n].get('level')==2]
    while len(level2_nodes) < target_level2_size:
        G.add_node(max_node_id, level=2)
        G.add_edge(root, max_node_id)
        level2_nodes.append(max_node_id)
        max_node_id += 1
        added += 1

    for n2 in level2_nodes:
        children_level3 = [c for c in G.successors(n2) if G.nodes[c].get('level')==3]
        while len(children_level3) < target_level3_size:
            G.add_node(max_node_id, level=3)
            G.add_edge(n2, max_node_id)
            children_level3.append(max_node_id)
            max_node_id += 1
            added += 1

    return max_node_id, added

# 6. Симуляция внешних шоков 
def generate_shock_sequence(T,r_base=0.1,A_base=100,r_vol=0.08,A_vol=25,seed=None):
    if seed is not None:
        np.random.seed(seed)
    r_seq=[r_base]
    A_seq=[A_base]
    for t in range(1,T):
        r_new = r_seq[-1]+np.random.uniform(-r_vol,r_vol)
        A_new = A_seq[-1]+np.random.uniform(-A_vol,A_vol)
        r_seq.append(np.clip(r_new,-0.05,0.4))
        A_seq.append(np.clip(A_new,40,180))
    return list(zip(r_seq,A_seq))

# 7. Динамическая симуляция
def run_dynamic_simulation(T=20,level2_size=4,level3_size=4,c=10,B=1,seed=42,cost_noise=0.08):
    shock_seq = generate_shock_sequence(T,seed=seed)
    initial_G = generate_mesomarket(level2_size,level3_size)
    G = initial_G.copy()
    max_node_id = max(G.nodes)+1

    max_node_id, _ = enforce_hierarchy(G, max_node_id, target_level2_size=level2_size, target_level3_size=level3_size)
    history = []
    prev_r, prev_A = shock_seq[0]
    for t in range(T):
        r, A = shock_seq[t]
        assign_costs(G, c, cost_noise)
        compute_prices(G, r)
        compute_production_volumes(G, A, B)
        compute_flows(G)
        compute_profits(G)

        # 1. Вход фирм - если спрос растет
        entries = 0
        if A > prev_A:
            delta = A - prev_A
            max_new = max(4, level2_size * level3_size // 2)
            n_new = min(max_new, max(1, int(delta / 5)))
            max_node_id, added = add_firms_on_demand(G, max_node_id, n_new=n_new, per_level2_limit=level3_size)
            entries = added

        # 2. Выход фирм - если процентная ставка растет (убираем фирмы, у которых прибыль ниже средней за последние 5 шагов)
        exits = 0
        if r > prev_r and t >= 5:
            last5_avgs = [h['avg_profit_lvl3'] for h in history[-5:] if 'avg_profit_lvl3' in h]
            if last5_avgs:
                avg5 = np.mean(last5_avgs)
                lvl3 = [n for n in G.nodes if G.nodes[n].get('level') == 3]
                to_remove = [n for n in lvl3 if G.nodes[n].get('profit', 0) < avg5]
                for n in to_remove:
                    G.remove_node(n)
                exits = len(to_remove)

        # 3. Перестройка связей - если средняя прибыль фирм уровня 3 ниже медианы за последние 5 шагов
        rewirings = 0
        lvl3_profits = [G.nodes[n].get('profit', 0) for n in G.nodes if G.nodes[n].get('level') == 3]
        avg_profit_lvl3 = np.mean(lvl3_profits) if lvl3_profits else 0
        if t >= 5:
            last5 = [h['avg_profit_lvl3'] for h in history[-5:] if 'avg_profit_lvl3' in h]
            if last5 and avg_profit_lvl3 < np.median(last5):
                rewirings = rewire_connections(G)

        max_node_id, added_protection = ensure_level2_has_child(G, max_node_id)

        # Считаем метрики после структурной перестройки 
        metrics = {
            't': t, 'r': r, 'A': A,
            'avg_price': np.mean([G.nodes[n].get('price', 10) for n in G.nodes]) if G.number_of_nodes() > 0 else 0,
            'avg_quantity': np.mean([G.nodes[n].get('quantity', 0) for n in G.nodes]) if G.number_of_nodes() > 0 else 0,
            'total_quantity': sum([G.nodes[n].get('quantity', 0) for n in G.nodes]),
            'total_money_flow': sum([G.edges[e].get('money_flow', 0) for e in G.edges]),
            'num_nodes': G.number_of_nodes(),
            'num_edges': G.number_of_edges(),
            'avg_profit_lvl3': avg_profit_lvl3
        }

        metrics['exits'] = exits
        metrics['entries'] = entries
        metrics['rewirings'] = rewirings
        metrics['added_to_protect_level2'] = added_protection

        history.append(metrics)

        prev_r, prev_A = r, A

    return history,G,initial_G,shock_seq

# 8. Визуализация результатов
def hierarchy_pos(G, root=0, width=1.0, vert_gap=0.3, vert_loc=0, xcenter=0.5):
    pos = {}
    def _hierarchy_pos(node,width,vert_loc,xcenter):
        pos[node]=(xcenter,vert_loc)
        children=list(G.successors(node))
        if children:
            dx = width/max(1,len(children))
            nextx=xcenter-width/2+dx/2
            for child in children:
                _hierarchy_pos(child,dx,vert_loc-vert_gap,nextx)
                nextx+=dx
    try:
        root_node = root if root in G.nodes else list(G.nodes)[0]
        _hierarchy_pos(root_node,width,vert_loc,xcenter)
    except:
        pos=nx.spring_layout(G,seed=42)
    return pos

def plot_network_comparison(initial_G,final_G):
    fig,axes=plt.subplots(1,2,figsize=(18,8))

    # Начальная сеть
    pos_init=hierarchy_pos(initial_G)
    nx.draw_networkx_nodes(initial_G, pos_init, node_color='#1F1777', node_size=600, ax=axes[0], edgecolors='none', linewidths=0)
    nx.draw_networkx_edges(initial_G, pos_init, edge_color='#1F1777', arrows=True, arrowsize=15, ax=axes[0])
    nx.draw_networkx_labels(initial_G, pos_init, font_size=11, ax=axes[0], font_color='white', font_weight='bold')
    axes[0].set_title(f"Начальная сеть: {initial_G.number_of_nodes()} узлов, {initial_G.number_of_edges()} связей")
    axes[0].axis('off')

    # Конечная сеть 
    pos_fin=hierarchy_pos(final_G)
    init_nodes=set(initial_G.nodes)
    fin_nodes=set(final_G.nodes)
    preserved=init_nodes&fin_nodes
    new_nodes=fin_nodes-init_nodes
    nx.draw_networkx_nodes(final_G, pos_fin, nodelist=list(preserved), node_color='#1F1777', node_size=550, ax=axes[1], edgecolors='none', linewidths=0)
    if new_nodes:
        nx.draw_networkx_nodes(final_G, pos_fin, nodelist=list(new_nodes), node_color='#FA499F', node_size=550, edgecolors='none', linewidths=0, ax=axes[1])
    nx.draw_networkx_edges(final_G, pos_fin, edge_color='#1F1777', arrows=True, arrowsize=15, alpha=0.5, ax=axes[1])
    nx.draw_networkx_labels(final_G, pos_fin, font_size=11, ax=axes[1], font_color='white', font_weight='bold')
    axes[1].set_title(f"Конечная сеть: {final_G.number_of_nodes()} узлов, {final_G.number_of_edges()} связей")
    axes[1].axis('off')
    plt.tight_layout()
    plt.show()

def plot_dynamic_results(history,shock_seq):
    t=[h['t'] for h in history]
    fig,axes=plt.subplots(2,2,figsize=(14,8))
    # Средняя цена
    axes[0,0].plot(t,[h['avg_price'] for h in history],color='#1F1777')
    axes[0,0].set_title('Средняя цена')
    axes[0,0].grid(True)
    # Средний объем
    axes[0,1].plot(t,[h['avg_quantity'] for h in history],color='#1F1777')
    axes[0,1].set_title('Средний объем производства')
    axes[0,1].grid(True)
    # Совокупный денежный поток
    axes[1,0].plot(t,[h['total_money_flow'] for h in history],color='#1F1777')
    axes[1,0].set_title('Совокупный денежный поток')
    axes[1,0].grid(True)
    # Совокупный объем призводства 
    axes[1,1].plot(t,[h['total_quantity'] for h in history],color='#1F1777')
    axes[1,1].set_title('Совокупный объем производства')
    axes[1,1].grid(True)

    plt.tight_layout()
    plt.show()

# Изменение процентной ставки, спроса и сигналов перестройки
def plot_shocks_and_rewirings(history, shock_seq):
    t = [h['t'] for h in history]
    r = [h['r'] for h in history]
    A = [h['A'] for h in history]
    rewire_steps = [h['t'] for h in history if h.get('rewirings', 0) > 0]

    fig, ax1 = plt.subplots(figsize=(12, 6))

    ax1.set_ylabel('Процентная ставка (r)', color='#1F1777')
    ax1.plot(t, r, color='#1F1777', label='Процентная ставка r')
    ax1.tick_params(axis='y', labelcolor='#1F1777')

    ax2 = ax1.twinx()
    ax2.set_ylabel('Спрос (A)', color='#FA499F')
    ax2.plot(t, A, color='#FA499F', label='Спрос A')
    ax2.tick_params(axis='y', labelcolor='#FA499F')

    # Отмечаем вертикальными линиями шаги, когда была перестройка сети
    for step in rewire_steps:
        ax1.axvline(step, color='#1F1777', linestyle='--', alpha=0.4, lw=1)

    fig.tight_layout()
    plt.show()

history, final_G, initial_G, shock_seq = run_dynamic_simulation(T=20)
plot_network_comparison(initial_G,final_G)
plot_dynamic_results(history,shock_seq)
plot_shocks_and_rewirings(history, shock_seq)
