# en este archivo se crearan las simulaciones de inventario DIARIO y la sumatoria de costos
# se necesita:
# - función de disminución de inventario por demanda 
# - función de reposición de inventario
# - función que calcule el costo diario
# - función que calcule el costo total
def simulacion_unificada(distribuciones_tienda, distribuciones_zona,
                         ventas_tienda, ventas_zona, reorden,
                         dias_simulados=10, frecuencia_reabastecimiento=5,
                         costo_inventario_unitario=3.733, reorden_multiplicador=1.0, semilla=42):

    np.random.seed(semilla)

    # Ajustar reorden
    reorden_mod = reorden.copy()
    reorden_mod['reorden'] = (reorden_mod['reorden'] * reorden_multiplicador).clip(lower=1).astype(int)

    # Diccionarios rápidos
    dist_tienda_dict = distribuciones_tienda.set_index('id_producto')[['mejor_ajuste', 'parametro1', 'parametro2']].to_dict('index')
    dist_zona_dict = distribuciones_zona.set_index('id_producto')[['mejor_ajuste', 'parametro1', 'parametro2']].to_dict('index')

    # Inicializar stock
    stock = reorden_mod[['id_tienda', 'id_producto', 'reorden']].copy()
    stock['stock_actual'] = stock['reorden']
    stock.set_index(['id_tienda', 'id_producto'], inplace=True)
    stock_dia = []

    registro_dia_a_dia = []
    costos_diarios = []

    for dia in range(1, dias_simulados + 1):
        vt = ventas_tienda[ventas_tienda['dia'] == dia][['id_tienda', 'id_producto', 'cantidad']]
        vz = ventas_zona[ventas_zona['dia'] == dia][['id_tienda', 'id_producto', 'cantidad']]
        demanda = pd.concat([vt, vz], ignore_index=True)

        demanda_total = demanda.groupby(['id_tienda', 'id_producto'])['cantidad'].sum().reset_index()

        # Generar variación estocástica
        demanda_total['variacion'] = demanda_total.apply(
            lambda row: generar_variacion_estocastica(
                *(dist_tienda_dict.get(row['id_producto']) or dist_zona_dict.get(row['id_producto']) or ('Constante', 1.0, None))
            ),
            axis=1
        )
        demanda_total['cantidad_ajustada'] = (demanda_total['cantidad'] * demanda_total['variacion']).round().astype(int)

        for _, row in demanda_total.iterrows():
            clave = (row['id_tienda'], row['id_producto'])
            if clave in stock.index:
                disponible = stock.at[clave, 'stock_actual']
                atendido = min(disponible, row['cantidad_ajustada'])
                no_atendido = row['cantidad_ajustada'] - atendido
                stock.at[clave, 'stock_actual'] -= atendido

                registro_dia_a_dia.append({
                    'dia': dia,
                    'id_tienda': row['id_tienda'],
                    'id_producto': row['id_producto'],
                    'demanda': row['cantidad_ajustada'],
                    'atendido': atendido,
                    'no_atendido': no_atendido,
                    'stock_restante': stock.at[clave, 'stock_actual']
                })

        stock_total = stock['stock_actual'].sum()
        costos_diarios.append(stock_total * costo_inventario_unitario)

        df_stock_dia = stock.reset_index().copy()
        df_stock_dia['dia'] = dia
        df_stock_dia['reorden'] = reorden_mod.set_index(['id_tienda', 'id_producto']).loc[stock.index, 'reorden'].values
        stock_dia.append(df_stock_dia)
        

        if dia % frecuencia_reabastecimiento == 0:
            stock['stock_actual'] += stock['reorden'] - stock['stock_actual']

    resultados_df = pd.DataFrame(registro_dia_a_dia)
    df_stock_diario = pd.concat(stock_dia, ignore_index=True)
    
    demanda_total = resultados_df['demanda'].sum()
    atendido_total = resultados_df['atendido'].sum()
    no_atendido_total = resultados_df['no_atendido'].sum()
    costo_total = sum(costos_diarios)
    

    return {
        'nivel_servicio': atendido_total / demanda_total if demanda_total > 0 else 0,
        'costo_total': costo_total,
        'costo_diario_promedio': costo_total / dias_simulados,
        'demanda_no_atendida_total': no_atendido_total,
        'costos_diarios': costos_diarios,
        'registro_dia_a_dia': resultados_df,
        'stock_diario': df_stock_diario
    }
