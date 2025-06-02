
import streamlit as st
from datetime import datetime
import openrouteservice
from openrouteservice import exceptions as ors_exceptions
import pandas as pd

# Tenta importar Pydeck e define 'pdk'
try:
    import pydeck as pdk
    PYDECK_AVAILABLE = True
except ImportError:
    PYDECK_AVAILABLE = False
    pdk = None 


# No início do seu app.py, após os imports

# ----- CONFIGURAÇÃO DO CLIENTE OPENROUTESERVICE (COM ST.SECRETS) -----
ORS_API_KEY = st.secrets.get("ORS_API_KEY", None) # Tenta pegar a chave dos secrets
ORS_CLIENT_VALID = False
ors_client = None 

if ORS_API_KEY:
    try:
        ors_client = openrouteservice.Client(key=ORS_API_KEY)
        ORS_CLIENT_VALID = True
        # Opcional: st.toast("Cliente ORS inicializado com sucesso via secrets!", icon="✅")
    except Exception as e:
        # Este erro será mais visível se ocorrer durante a execução da lógica
        # st.error(f"Falha ao inicializar o cliente OpenRouteService com a chave dos secrets: {e}")
        ORS_CLIENT_VALID = False # Garante que está False se a inicialização falhar
else:
    # Este aviso aparecerá na interface do app se a chave não estiver nos secrets
    # Não precisa de st.error aqui, pois o aviso no corpo do app já informa.
    pass 
# ----- FIM DA CONFIGURAÇÃO ORS -----

# ----- INÍCIO DAS DEFINIÇÕES DE DADOS E FUNÇÕES -----
tabela_antt = {
    'PORTARIA Nº 3, DE 7 DE fevereiro DE 2025': [7.639, 623.070, '07/02/2025'],
    'RESOLUÇÃO Nº 6.046, DE 11 DE JULHO DE 2024': [7.486, 675.050, '11/07/2024'],
    'RESOLUÇÃO Nº 6.034, DE 18 DE JANEIRO DE 2024': [7.413, 664.970, '18/01/2024'],
    'PORTARIA Nº 20, DE 28 DE AGOSTO DE 2023': [7.277, 618.410, '28/08/2023'],
    'PORTARIA Nº 19, DE 21 DE AGOSTO DE 2023': [6.933, 618.410, '21/08/2023'],
    'RESOLUÇÃO Nº 6.022, DE 20 DE JULHO DE 2023': [6.646, 618.410, '20/07/2023'],
    'PORTARIA Nº 13, DE 5 DE JUNHO DE 2023': [6.608, 597.020, '05/06/2023'],
    'PORTARIA Nº 11, DE 22 DE MAIO DE 2023': [6.795, 597.020, '22/05/2023'],
    'PORTARIA Nº 8, DE 25 DE ABRIL DE 2023': [7.001, 597.020, '25/04/2023'],
    'PORTARIA Nº 5, DE 17 DE FEVEREIRO DE 2023': [7.195, 597.020, '07/02/2023'],
    'RESOLUÇÃO Nº 6.006, DE 19 DE JANEIRO DE 2023': [7.426, 597.020, '19/01/2023'],
    'PORTARIA SUROC Nº 219, DE 3 DE OUTUBRO DE 2022': [6.938, 463.840, '03/10/2022'],
    'PORTARIA Nº 214, DE 22 DE AGOSTO DE 2022': [7.188, 463.840, '22/08/2022'],
    'RESOLUÇÃO Nº 5.985, DE 19 DE JULHO DE 2022': [7.471, 463.840, '19/07/2022'],
    'PORTARIA Nº 210, DE 24 DE JUNHO DE 2022': [7.381, 436.580, '24/06/2022'],
    'PORTARIA Nº 169, DE 18 DE MARÇO DE 2022': [6.802, 436.580, '18/03/2022'],
    'RESOLUÇÃO Nº 5.959, DE 20 DE JANEIRO DE 2022': [5.969, 436.580, '20/01/2022'],
    'PORTARIA Nº 496, DE 19 DE OUTUBRO DE 2021': [5.436, 398.380, '19/10/2021'],
    'RESOLUÇÃO Nº 5.949, DE 13 DE JULHO DE 2021': [5.145, 398.380, '13/07/2021'],
    'RESOLUÇÃO Nº 5.923, DE 18 DE JANEIRO DE 2021': [4.487, 380.860, '18/01/2021'],
    'PORTARIA Nº 399, DE 3 DE NOVEMBRO DE 2020': [4.380, 369.700, '03/11/2020'],
    'RESOLUÇÃO Nº 5.899, DE 14 DE JULHO DE 2020': [4.099, 369.700, '14/07/2020'],
    'RESOLUÇÃO Nº 5.890, DE 26 DE MAIO DE 2020': [4.423, 413.790, '26/05/2020']
}

def encontrar_frete_vigente(tabela, data_requisicao_str):
    try:
        data_req_obj = datetime.strptime(data_requisicao_str, '%d/%m/%Y')
    except ValueError:
        return None, None, None
    entradas_ordenadas = []
    for normativo, valores in tabela.items():
        data_normativo_str = valores[2]
        try:
            data_normativo_obj = datetime.strptime(data_normativo_str, '%d/%m/%Y')
            entradas_ordenadas.append((data_normativo_obj, normativo, [valores[0], valores[1]]))
        except ValueError:
            continue
    if not entradas_ordenadas: 
        return None, None, data_req_obj
    entradas_ordenadas.sort(key=lambda item: item[0])
    frete_aplicavel = None
    normativo_aplicavel = None
    if data_req_obj < entradas_ordenadas[0][0]:
        return None, None, data_req_obj
    for i in range(len(entradas_ordenadas)):
        data_normativo_atual, normativo_atual, frete_atual = entradas_ordenadas[i]
        if data_req_obj >= data_normativo_atual:
            frete_aplicavel = frete_atual
            normativo_aplicavel = normativo_atual
            if (i + 1 == len(entradas_ordenadas)) or (data_req_obj < entradas_ordenadas[i+1][0]):
                break
    return normativo_aplicavel, frete_aplicavel, data_req_obj

def obter_coordenadas_ors(nome_lugar, client_ors_func):
    global ORS_CLIENT_VALID
    if not ORS_CLIENT_VALID or not client_ors_func:
        st.session_state.ors_log.append(f"⚠️ ORS: Cliente não válido para geocodificar '{nome_lugar}'.")
        return None
    try:
        geocode_result = client_ors_func.pelias_search(text=nome_lugar, size=1)
        if geocode_result and geocode_result.get('features'):
            coordenadas = geocode_result['features'][0]['geometry']['coordinates']
            st.session_state.ors_log.append(f"✔️ Coordenadas para '{nome_lugar}': {coordenadas}")
            return coordenadas
        else:
            st.session_state.ors_log.append(f"⚠️ ORS: Não encontrou coordenadas para '{nome_lugar}'.")
            return None
    except ors_exceptions.RateLimitExceeded as rle: # Tratamento específico para limite de taxa
        st.session_state.ors_log.append(f"❌ ORS API Error (geocoding '{nome_lugar}'): Limite de taxa excedido. {rle}")
        ORS_CLIENT_VALID = False 
        st.error("ORS: Limite de requisições da API atingido. Tente novamente mais tarde.")
        return None
    except ors_exceptions.ApiError as e:
        st.session_state.ors_log.append(f"❌ ORS API Error (geocoding '{nome_lugar}'): {e}")
        return None
    except Exception as e:
        st.session_state.ors_log.append(f"❌ ORS Unexpected Error (geocoding '{nome_lugar}'): {e}")
        return None

def calcular_rota_e_distancia_ors(nome_origem_str, nome_destino_str, client_ors_func):
    global ORS_CLIENT_VALID
    st.session_state.ors_log = [f"Iniciando cálculo de rota ORS: '{nome_origem_str}' -> '{nome_destino_str}'"]
    
    if not ORS_CLIENT_VALID or not client_ors_func:
        st.session_state.ors_log.append("⚠️ ORS: Cliente não válido para cálculo de rota.")
        return None, None, None, None # distancia, coords_o, coords_d, route_geometry

    coords_origem = obter_coordenadas_ors(nome_origem_str, client_ors_func)
    if not ORS_CLIENT_VALID: return None, coords_origem, None, None

    coords_destino = obter_coordenadas_ors(nome_destino_str, client_ors_func)
    if not ORS_CLIENT_VALID: return None, coords_origem, coords_destino, None

    if coords_origem and coords_destino:
        try:
            st.session_state.ors_log.append(f" Tentando obter rota entre {coords_origem} e {coords_destino}...")
            rota_result = client_ors_func.directions(
                coordinates=[coords_origem, coords_destino],
                profile="driving-car", format="geojson", geometry="true" # Solicita a geometria
            )
            if rota_result and rota_result.get('features'):
                feature = rota_result['features'][0]
                distancia_metros = feature['properties']['segments'][0]['distance']
                distancia_km = distancia_metros / 1000
                route_geometry = feature['geometry']['coordinates'] # Lista de [lon, lat]
                st.session_state.ors_log.append(f"✔️ ORS: Distância: {distancia_km:.2f} km. Geometria da rota obtida.")
                return distancia_km, coords_origem, coords_destino, route_geometry
            else:
                st.session_state.ors_log.append(f"❌ ORS Error: Resposta da rota inesperada ou vazia.")
                return None, coords_origem, coords_destino, None
        except ors_exceptions.RateLimitExceeded as rle:
            st.session_state.ors_log.append(f"❌ ORS API Error (routing): Limite de taxa excedido. {rle}")
            ORS_CLIENT_VALID = False
            st.error("ORS: Limite de requisições da API atingido. Tente novamente mais tarde.")
            return None, coords_origem, coords_destino, None
        except ors_exceptions.ApiError as e:
            st.session_state.ors_log.append(f"❌ ORS API Error (routing): {e}")
            if hasattr(e, 'response') and e.response is not None:
                 st.session_state.ors_log.append(f"Detalhes: {e.response.text}")
            return None, coords_origem, coords_destino, None
        except (KeyError, IndexError, TypeError) as e:
            st.session_state.ors_log.append(f"❌ ORS Error (processando resposta da rota): {e}")
            return None, coords_origem, coords_destino, None
    else:
        st.session_state.ors_log.append("⚠️ ORS: Rota não calculada (origem ou destino não geocodificado).")
        return None, coords_origem, coords_destino, None
# ----- FIM DAS DEFINIÇÕES DE DADOS E FUNÇÕES -----

st.set_page_config(layout="wide", page_title="Calculadora de Frete ANTT")
st.title("Cálculo de Frete ANTT e Distância 🚚")

if not ORS_CLIENT_VALID:
    st.error("Cliente OpenRouteService não inicializado ou chave API inválida/não configurada. Funcionalidade de distância e mapa estarão desabilitadas.")

if 'ors_log' not in st.session_state: st.session_state.ors_log = []
if 'map_data' not in st.session_state: 
    st.session_state.map_data = {'points': None, 'route': None}

with st.form(key="input_form"):
    st.markdown("##### 🗓️ Data e 🌍 Localidades")
    col_data, col_origem, col_destino = st.columns(3)
    with col_data:
        data_selecionada_dt = st.date_input("Data da requisição:", datetime.now(), help="Selecione a data para o cálculo.")
        if data_selecionada_dt: # Feedback visual do formato da data
             st.caption(f"Formato para cálculo: **{data_selecionada_dt.strftime('%d/%m/%Y')}**")
    with col_origem:
        origem_nome_input = st.text_input("Local de Origem:", value="Fortaleza, CE, Brasil", help="Ex: Fortaleza, CE ou Praça do Ferreira, Fortaleza")
    with col_destino:
        destino_nome_input = st.text_input("Local de Destino:", value="São Paulo, SP, Brasil", help="Ex: São Paulo, SP ou Parque Ibirapuera, São Paulo")
    
    st.markdown("---")
    st.markdown("##### 💰 Adicionais Personalizados")
    col_adic1, col_adic2 = st.columns(2)
    with col_adic1:
        valor_dificuldade_input = st.number_input("Valor por Dificuldade (R$):", 
                                            min_value=0.0, value=0.0, format="%.2f",
                                            help="Valor fixo somado devido a dificuldades na rota/operação.")
    with col_adic2:
        adicional_deslocamento_taxa_input = st.number_input("Adicional por deslocamento (R$/km):", 
                                                      min_value=0.0, value=0.0, format="%.3f",
                                                      help="Taxa extra por km multiplicada pela distância.")
    st.markdown("---")
    submit_button = st.form_submit_button("Calcular Frete e Distância 🧮", disabled=not ORS_CLIENT_VALID)

if submit_button:
    data_usuario_str = data_selecionada_dt.strftime('%d/%m/%Y')
    valid_input = True
    if not origem_nome_input.strip() or not destino_nome_input.strip():
        st.error("Por favor, preencha os nomes dos locais de origem e destino.")
        valid_input = False
    
    if valid_input and ORS_CLIENT_VALID:
        with st.spinner("Calculando distância via ORS e frete... ⏳"):
            distancia, coords_o, coords_d, route_geom = calcular_rota_e_distancia_ors(origem_nome_input, destino_nome_input, ors_client)
            
            # Prepara dados para o mapa
            map_points_list = []
            if coords_o: map_points_list.append({'latitude': coords_o[1], 'longitude': coords_o[0], 'tipo': 'Origem', 'cor': [200, 30, 0, 200]}) # Vermelho para origem
            if coords_d: map_points_list.append({'latitude': coords_d[1], 'longitude': coords_d[0], 'tipo': 'Destino', 'cor': [0, 0, 255, 200]}) # Azul para destino
            
            st.session_state.map_data['points'] = pd.DataFrame(map_points_list) if map_points_list else None
            st.session_state.map_data['route'] = [{"path": route_geom, "name": "Rota Calculada"}] if route_geom else None

            normativo, frete_componentes, data_obj = encontrar_frete_vigente(tabela_antt, data_usuario_str)

            st.markdown("---") 
            st.subheader("📊 RESULTADOS DO CÁLCULO")
            
            # Informações básicas
            res_col1, res_col2 = st.columns(2)
            with res_col1:
                st.markdown(f"**Data da Requisição:** `{data_usuario_str}`")
                st.markdown(f"**Origem Informada:** `{origem_nome_input}`")
            with res_col2:
                st.markdown(f"**Destino Informado:** `{destino_nome_input}`")
                if distancia is not None:
                    st.metric(label="Distância Calculada (ORS)", value=f"{distancia:.2f} km")
                else:
                    st.error("Distância não pôde ser calculada via ORS.")
            st.markdown("---")

            # Cálculo e exibição do frete
            if data_obj is None: 
                st.error("ERRO: Formato de data inválido para a requisição.")
            elif normativo and frete_componentes:
                coef_desloc_antt = frete_componentes[0]
                valor_fixo_cd_antt = frete_componentes[1]

                st.markdown("#### 📜 Componentes do Frete Base (ANTT)")
                st.info(f"**Normativo Aplicável:** {normativo}")
                f_col1, f_col2 = st.columns(2)
                f_col1.metric("R$ / km (Base ANTT)", f"{coef_desloc_antt:.3f}")
                f_col2.metric("Valor Fixo Carga/Descarga (ANTT)", f"R$ {valor_fixo_cd_antt:.2f}")

                if distancia is not None and distancia > 0:
                    custo_deslocamento_antt = coef_desloc_antt * distancia
                    custo_adicional_desloc = adicional_deslocamento_taxa_input * distancia
                    frete_total_calculado = (custo_deslocamento_antt + valor_fixo_cd_antt + 
                                             custo_adicional_desloc + valor_dificuldade_input)
                    frete_real_por_km = frete_total_calculado / distancia
                    delta_vs_base = frete_real_por_km - coef_desloc_antt
                    percent_change = (delta_vs_base / coef_desloc_antt * 100) if coef_desloc_antt > 0 else 0
                    
                    delta_color = "off" # Cinza para neutro/igual
                    arrow = "➖"
                    if delta_vs_base > 0.001: # Pequena tolerância para flutuação
                        delta_color = "normal" # Verde (padrão para positivo)
                        arrow = "⬆️"
                    elif delta_vs_base < -0.001:
                        delta_color = "inverse" # Vermelho (padrão para negativo)
                        arrow = "⬇️"

                    st.markdown("#### 💰 Cálculos de Frete Detalhados")
                    det_cols = st.columns(4)
                    det_cols[0].metric("Custo Desloc. (ANTT)", f"R$ {custo_deslocamento_antt:.2f}")
                    det_cols[1].metric("Custo Adic. Desloc.", f"R$ {custo_adicional_desloc:.2f}", help=f"{adicional_deslocamento_taxa_input:.3f} R$/km * {distancia:.2f} km")
                    det_cols[2].metric("Valor por Dificuldade", f"R$ {valor_dificuldade_input:.2f}")
                    # O "Valor Fixo Carga/Descarga (ANTT)" já está como métrica acima.
                                    
                    st.markdown("---")
                    st.subheader("Estimativas Finais do Frete:")
                    final_col1, final_col2 = st.columns(2)
                    final_col1.metric("Valor Total Final Estimado", f"R$ {frete_total_calculado:.2f}")
                    final_col2.metric(label=f"Frete Real (R$/km Total) {arrow}", 
                                      value=f"R$ {frete_real_por_km:.3f}",
                                      delta=f"{percent_change:.1f}% vs Base ANTT", 
                                      delta_color=delta_color)
                
                elif distancia == 0: # Distância é zero
                    st.warning("Distância calculada é 0 km. Cálculos de R$/km não aplicáveis.")
                    custos_fixos_total = valor_fixo_cd_antt + valor_dificuldade_input
                    st.metric("Valor Total Estimado (Custos Fixos)", f"R$ {custos_fixos_total:.2f}")
                else: # Distancia is None
                    st.warning("Sem distância calculada, não é possível detalhar custos variáveis ou o 'Frete Real'.")
                    st.markdown(f"**Valor Fixo Carga/Descarga (ANTT):** R$ {valor_fixo_cd_antt:.2f}")
                    st.markdown(f"**Adicional por Dificuldade (informado):** R$ {valor_dificuldade_input:.2f}")

            elif not (data_obj is None): 
                st.warning(f"Nenhuma tabela de frete ANTT para a data {data_usuario_str}.")
            
            # --- Exibição do Mapa ---
            st.markdown("---")
            st.subheader("🗺️ Mapa da Rota Estimada")
            map_df = st.session_state.map_data.get('points')
            route_data = st.session_state.map_data.get('route')

            if map_df is not None and not map_df.empty:
                # Centralizar o mapa
                if len(map_df) >= 1:
                    center_lat = map_df['latitude'].mean()
                    center_lon = map_df['longitude'].mean()
                    initial_zoom = 3 if len(map_df) == 2 and distancia and distancia > 500 else 10 if len(map_df)==1 else 5
                else: # Fallback se não houver pontos
                    center_lat = -15.788497 # Centro aproximado do Brasil
                    center_lon = -47.879873 
                    initial_zoom = 3

                layers_map = []
                # Camada de Pontos (Origem e Destino)
                layers_map.append(pdk.Layer(
                    'ScatterplotLayer',
                    data=map_df,
                    get_position='[longitude, latitude]',
                    get_fill_color='cor', # Usa a coluna 'cor' definida ao criar o DataFrame
                    get_radius=25000 if PYDECK_AVAILABLE else 10000, # Raio em metros, ajuste
                    pickable=True,
                    tooltip={"html": "<b>{tipo}</b><br/>Lat: {latitude}<br/>Lon: {longitude}"}
                ))

                # Camada da Rota
                if PYDECK_AVAILABLE and pdk is not None and route_data:
                    layers_map.append(pdk.Layer(
                        "PathLayer",
                        data=route_data,
                        get_path="path", # A chave que contém a lista de coordenadas
                        get_width=15, # Largura da linha em pixels no mapa
                        get_color=[0, 100, 255, 180], # Azul para a rota
                        width_min_pixels=2,
                        pickable=True,
                        tooltip={"html": "<b>{name}</b>"}
                    ))
                
                if PYDECK_AVAILABLE and pdk is not None:
                    try:
                        st.pydeck_chart(pdk.Deck(
                            map_style='mapbox://styles/mapbox/light-v9', # Ou 'dark-v9', ou None para padrão
                            initial_view_state=pdk.ViewState(
                                latitude=center_lat,
                                longitude=center_lon,
                                zoom=initial_zoom, 
                                pitch=45, # Ângulo de visão
                                bearing=0
                            ),
                            layers=layers_map,
                            tooltip={"html": "<b>{tipo}</b><br/>Lat: {latitude}<br/>Lon: {longitude}", 
                                     "style": {"backgroundColor": "steelblue", "color": "white"}}
                        ))
                    except Exception as e_map:
                        st.error(f"Erro ao gerar mapa com Pydeck: {e_map}. Usando st.map como fallback se possível.")
                        if not map_df.empty: st.map(map_df, zoom=initial_zoom) # Fallback
                
                elif not map_df.empty : # Se Pydeck não disponível, mas temos pontos, usa st.map
                    st.map(map_df, zoom=initial_zoom)
            else:
                st.caption("Coordenadas não disponíveis para exibir o mapa.")

            # Exibir logs do ORS
            with st.expander("🔍 Ver Log de Processamento OpenRouteService", expanded=False):
                if st.session_state.ors_log:
                    for msg in st.session_state.ors_log:
                        if "✔️" in msg: st.success(msg)
                        elif "⚠️" in msg: st.warning(msg)
                        elif "❌" in msg: st.error(msg)
                        else: st.text(msg)
                else:
                    st.caption("Nenhuma mensagem de log do ORS gerada.")
    elif not ORS_CLIENT_VALID:
        st.error("Cálculo não pode prosseguir: Cliente OpenRouteService não inicializado.")

