import networkx as nx
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from collections import defaultdict
import random

# 1. Генерация иерархического мезорынка
def generate_mesomarket(levels=3, branching=4):
    """
    Создает иерархический ориентированный граф мезорынка.
    Узлы - микрорынки, рёбра - потоки товаров и денег.
    
    Параметры:
    -----------
    levels : int
        Глубина иерархии сети (по умолчанию 3)
    branching : int
        Интенсивность конкуренции - количество дочерних узлов (по умолчанию 4)
    
    Результат:
    --------
    G : nx.DiGraph
        Ориентированный граф мезорынка
    """
    G = nx.DiGraph()
    node_id = 0
    
    # Корневой узел (уровень 0)
    current_level = [node_id]
    G.add_node(node_id, level=0)
    node_id += 1
    
    # Создание уровней иерархии
    for l in range(1, levels):
        next_level = []
        for parent in current_level:
            for _ in range(branching):
                G.add_node(node_id, level=l)
                G.add_edge(parent, node_id) 
                next_level.append(node_id)
                node_id += 1
        current_level = next_level
    
    return G


# 2. Расчет издержек и цен
def assign_costs(G, c=10):
    """
    Назначает издержки каждому микрорынку.
    Формула: cost = c * (1 + 0.2 * level)
    
    Параметры:
    -----------
    G : nx.DiGraph
        Граф мезорынка
    c : float
        Базовые издержки (по умолчанию 10)
    """
    for node in G.nodes:
        level = G.nodes[node]['level']
        cost = c * (1 + 0.2 * level)
        G.nodes[node]['cost'] = cost


def compute_prices(G, r):
    """
    Вычисляет цены для каждого микрорынка.
    Формула: price = (1 + r) * cost
    
    Параметры:
    -----------
    G : nx.DiGraph
        Граф мезорынка
    r : float
        Параметр процентной ставки (варьируется)
    """
    for node in G.nodes:
        cost = G.nodes[node]['cost']
        price = (1 + r) * cost
        G.nodes[node]['price'] = price


# 3. Расчет спроса и объемов производства
def demand_function(price, A, B=1):
    """
    Формула: D(p) = A - B * price
    
    Параметры:
    -----------
    price : float
        Цена товара
    A : float
        Параметр спроса (варьируется)
    B : float
        Коэффициент эластичности спроса (по умолчанию 1)
    
    Результат:
    --------
    float
        Объем спроса
    """
    return max(A - B * price, 0)

def compute_production_volumes(G, A, B=1):
    """
    Вычисляет объемы производства для каждого микрорынка.
    Формула: Q = D(p)
    
    Параметры:
    -----------
    G : nx.DiGraph
        Граф мезорынка
    A : float
        Параметр спроса
    B : float
        Коэффициент эластичности спроса
    """
    for node in G.nodes:
        price = G.nodes[node]['price']
        quantity = demand_function(price, A, B)
        G.nodes[node]['quantity'] = quantity


# 4. Модель потоков товаров и денег
def compute_flows(G):
    """
    Вычисляет потоки товаров и денег через сеть.
    Поток идет от родительских узлов к дочерним.
    
    Параметры:
    -----------
    G : nx.DiGraph
        Граф мезорынка
    """
    # Инициализация потоков
    for edge in G.edges:
        G.edges[edge]['goods_flow'] = 0
        G.edges[edge]['money_flow'] = 0
    
    # Вычисление потоков от корня к листья через топологическую сортировку
    try:
        topo_order = list(nx.topological_sort(G))
    except nx.NetworkXError:
        # Если есть циклы, используем простой порядок по уровням
        topo_order = sorted(G.nodes, key=lambda n: G.nodes[n]['level'])
    
    for node in topo_order:
        # Количество товара, доступное в узле
        if 'quantity' in G.nodes[node]:
            available_quantity = G.nodes[node]['quantity']
        else:
            available_quantity = 0
        
        # Распределение потока к дочерним узлам
        successors = list(G.successors(node))
        if successors:
            # Равномерное распределение потока между дочерними узлами
            flow_per_child = available_quantity / len(successors)
            for child in successors:
                G.edges[(node, child)]['goods_flow'] = flow_per_child
                # Денежный поток = поток товаров * цена дочернего узла
                child_price = G.nodes[child]['price']
                G.edges[(node, child)]['money_flow'] = flow_per_child * child_price


# 5. Симуляция внешних шоков
def simulate_shock(G, r, A, c=10, B=1):
    """
    Симулирует внешний шок при фиксированной структуре мезорынка.
    
    Параметры:
    -----------
    G : nx.DiGraph
        Граф мезорынка (структура не изменяется)
    r : float
        Процентная ставка (внешний шок)
    A : float
        Параметр спроса (внешний шок)
    c : float
        Базовые издержки
    B : float
        Коэффициент эластичности спроса
    
    Результат:
    --------
    dict
        Метрики рынка после шока
    """
    
    assign_costs(G, c)  # Фиксированная структура сети
    compute_prices(G, r)  # Влияние шока на цены через процентную ставку
    compute_production_volumes(G, A, B)  # Влияние шока на объемы через изменение спроса
    compute_flows(G)  # Вычисление потоков
    
    # Сбор метрик
    prices = [G.nodes[n]['price'] for n in G.nodes]
    quantities = [G.nodes[n].get('quantity', 0) for n in G.nodes]
    costs = [G.nodes[n]['cost'] for n in G.nodes]
    
    total_goods_flow = sum(G.edges[e]['goods_flow'] for e in G.edges)
    total_money_flow = sum(G.edges[e]['money_flow'] for e in G.edges)
    
    return {
        'avg_price': np.mean(prices),
        'avg_quantity': np.mean(quantities),
        'avg_cost': np.mean(costs),
        'total_quantity': sum(quantities),
        'total_goods_flow': total_goods_flow,
        'total_money_flow': total_money_flow,
        'price_variance': np.var(prices),
        'quantity_variance': np.var(quantities),
        'num_nodes': G.number_of_nodes(),
        'num_edges': G.number_of_edges()
    }


# 6. Анализ поведения мезорынка
def analyze_market_behavior(levels=3, branching=4, c=10, B=1):
    """
    Анализирует поведение мезорынка при изменении внешних шоков.
    
    Параметры:
    -----------
    levels : int
        Глубина иерархии
    branching : int
        Интенсивность конкуренции
    c : float
        Базовые издержки
    B : float
        Коэффициент эластичности спроса
    """
    
    G = generate_mesomarket(levels, branching)  # Создание фиксированной сети мезорынка
    
    # Сценарии внешних шоков
    scenarios = {
        'Базовый': {'r': 0.1, 'A': 100},
        'Рост процентной ставки': {'r': 0.2, 'A': 100},
        'Сильный рост процентной ставки': {'r': 0.3, 'A': 100},
        'Рост спроса': {'r': 0.1, 'A': 150},
        'Падение спроса': {'r': 0.1, 'A': 50},
        'Рост ставки + рост спроса': {'r': 0.2, 'A': 150},
        'Рост ставки + падение спроса': {'r': 0.2, 'A': 50},
    }
    
    results = {}
    for scenario_name, params in scenarios.items():
        # Создание копии графа для каждого сценария
        G_scenario = G.copy()
        metrics = simulate_shock(G_scenario, params['r'], params['A'], c, B)
        results[scenario_name] = {**params, **metrics}
    
    return results, G


# 7. Визуализация результатов
def plot_results(results, G):
    """
    Строит графики из результатов моделирования.
    
    Параметры:
    -----------
    results : dict
        Словарь с результатами по сценариям
    G : nx.DiGraph
        Граф мезорынка для визуализации структуры
    """
    scenario_names = list(results.keys())
    
    # Извлечение данных
    avg_prices = [results[s]['avg_price'] for s in scenario_names]
    avg_quantities = [results[s]['avg_quantity'] for s in scenario_names]
    total_quantities = [results[s]['total_quantity'] for s in scenario_names]
    total_money_flows = [results[s]['total_money_flow'] for s in scenario_names]
    
    # Фигура 1: Средняя цена и средний объем производства по сценариям
    fig1, (ax_price, ax_quantity) = plt.subplots(1, 2, figsize=(14, 5))

    ax_price.bar(range(len(scenario_names)), avg_prices, color="#1F1777")
    ax_price.set_title('Средняя цена по сценарию')
    ax_price.set_xticks(range(len(scenario_names)))
    ax_price.set_xticklabels(scenario_names, rotation=45, ha='right', fontsize=8)

    ax_quantity.bar(range(len(scenario_names)), avg_quantities, color="#1F1777")
    ax_quantity.set_title('Средний объем производства по сценарию')
    ax_quantity.set_xticks(range(len(scenario_names)))
    ax_quantity.set_xticklabels(scenario_names, rotation=45, ha='right', fontsize=8)

    fig1.tight_layout()

    # Фигура 2: Совокупный денежный поток и совокупный объем по сценариям
    fig2, (ax_money, ax_total) = plt.subplots(1, 2, figsize=(14, 5))

    ax_money.bar(range(len(scenario_names)), total_money_flows, color="#1F1777")
    ax_money.set_title('Совокупный денежный поток по сценарию')
    ax_money.set_xticks(range(len(scenario_names)))
    ax_money.set_xticklabels(scenario_names, rotation=45, ha='right', fontsize=8)

    ax_total.bar(range(len(scenario_names)), total_quantities, color="#1F1777")
    ax_total.set_title('Совокупный объем по сценарию')
    ax_total.set_xticks(range(len(scenario_names)))
    ax_total.set_xticklabels(scenario_names, rotation=45, ha='right', fontsize=8)

    fig2.tight_layout()


    # Фигура 2: Влияние внешних шоков
    fig2, (ax4, ax5, ax6) = plt.subplots(1, 3, figsize=(18, 5))
    
    # График 4: Влияние процентной ставки на цену
    r_range = np.linspace(0.05, 0.4, 20)
    prices_vs_r = []
    quantities_vs_r = []
    for r in r_range:
        G_temp = G.copy()
        metrics = simulate_shock(G_temp, r, A=100, c=10, B=1)
        prices_vs_r.append(metrics['avg_price'])
        quantities_vs_r.append(metrics['avg_quantity'])
    ax4.plot(r_range, prices_vs_r, color="#1F1777", linewidth=2, marker='o')
    ax4.set_xlabel('Процентная ставка (r)')
    ax4.set_ylabel('Средняя цена')
    ax4.set_title('Влияние процентной ставки на цену\n(при A = 100)')
    ax4.grid(True, alpha=0.3)
    
    # График 5: Влияние процентной ставки на объем
    ax5.plot(r_range, quantities_vs_r, color="#1F1777", linewidth=2, marker='o')
    ax5.set_xlabel('Процентная ставка (r)')
    ax5.set_ylabel('Средний объем производства')
    ax5.set_title('Влияние процентной ставки на объем\n(при A = 100)')
    ax5.grid(True, alpha=0.3)
    
    # График 6: Влияние спроса на объем
    A_range = np.linspace(30, 200, 20)
    quantities_vs_A = []
    for A in A_range:
        G_temp = G.copy()
        metrics = simulate_shock(G_temp, r=0.1, A=A, c=10, B=1)
        quantities_vs_A.append(metrics['avg_quantity'])
    ax6.plot(A_range, quantities_vs_A, color="#1F1777", linewidth=2, marker='o')
    ax6.set_xlabel('Спрос (A)')
    ax6.set_ylabel('Средний объем производства')
    ax6.set_title('Влияние спроса на объем\n(при r = 0.1)')
    ax6.grid(True, alpha=0.3)
    
    fig2.tight_layout()


    # Фигура 3: 3D-поверхность совокупного денежного потока
    r_grid = np.linspace(0.01, 0.5, 18)
    A_grid = np.linspace(10, 300, 18)
    R_grid, A_grid_mesh = np.meshgrid(r_grid, A_grid)

    # Сетка совокупного денежного потока
    Money_grid = np.zeros_like(R_grid)
    for i in range(len(A_grid)):
        for j in range(len(r_grid)):
            G_temp = G.copy()
            metrics = simulate_shock(G_temp, R_grid[i, j], A_grid_mesh[i, j], c=10, B=1)
            Money_grid[i, j] = metrics['total_money_flow']

    # 3D-поверхность
    colors = ["#2B1FAF", "#7368E8", '#C084FC', '#FA499F', "#FC97C8"]
    screenshot_cmap = LinearSegmentedColormap.from_list('screenshot_cmap', colors)

    fig3 = plt.figure(figsize=(10, 6))
    ax7 = fig3.add_subplot(111, projection='3d')
    surf = ax7.plot_surface(R_grid, A_grid_mesh, Money_grid, cmap=screenshot_cmap, linewidth=0.2, edgecolor="#1F1777", antialiased=True, alpha=0.95)
    
    ax7.set_zlabel('')
    ax7.set_zticklabels([]) 
    
    ax7.set_xlabel('Процентная ставка (r)')
    ax7.set_ylabel('Спрос (A)')
    ax7.set_title('Совокупный денежный поток = f(r, A)')

    cbar = fig3.colorbar(surf, ax=ax7, shrink=0.6, pad=0.1, label='Совокупный денежный поток')
    
    ax7.view_init(elev=30, azim=225)
    fig3.subplots_adjust(top=0.9, right=0.85)
    fig3.tight_layout()
    
    plt.show()


# 8. Основная функция для запуска моделирования
def main():
    # Анализ поведения рынка
    results, G = analyze_market_behavior(levels=3, branching=4, c=10, B=1)
    
    # Вывод результатов моделирования
    for scenario_name, metrics in results.items():
        print(f"\n{scenario_name}:")
        print(f"  r = {metrics['r']:.2f}, A = {metrics['A']:.1f}")
        print(f"  Средняя цена: {metrics['avg_price']:.2f}")
        print(f"  Средний объем: {metrics['avg_quantity']:.2f}")
        print(f"  Совокупный объем: {metrics['total_quantity']:.2f}")
        print(f"  Совокупный денежный поток: {metrics['total_money_flow']:.2f}")

    print("\nСтруктура мезорынка не изменилась")
    print(f"  узлов: {G.number_of_nodes()}")
    print(f"  рёбер: {G.number_of_edges()}")
    
    # Визуализация результатов
    plot_results(results, G)

if __name__ == "__main__":
    main()