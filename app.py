import streamlit as st
from datetime import datetime
import openrouteservice
from openrouteservice import exceptions as ors_exceptions
import pandas as pd

# Tenta importar Pydeck
try:
    import pydeck as pdk
    PYDECK_AVAILABLE = True
except ImportError:
    PYDECK_AVAILABLE = False
    pdk = None 

# ----- CONFIGURAÇÃO DO CLIENTE OPENROUTESERVICE -----
ORS_API_KEY = st.secrets.get("ORS_API_KEY", None) # Pega dos secrets do Streamlit Cloud
ORS_CLIENT_VALID = False
ors_client = None 
if ORS_API_KEY:
    try:
        ors_client = openrouteservice.Client(key=ORS_API_KEY)
        ORS_CLIENT_VALID = True
    except Exception as e:
        # Aviso será mostrado no corpo do app se a inicialização falhar
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

@st.cache_data # Cache para evitar recálculos desnecessários da taxa ANTT para a mesma data
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
    except ors_exceptions.ApiError as e:
        http_status = getattr(e, 'http_status', None) or getattr(e, 'status_code', None)
        st.session_state.ors_log.append(f"❌ ORS API Error (geocoding '{nome_lugar}'): HTTP {http_status if http_status else 'N/A'} - {e}")
        if http_status == 429:
            st.session_state.ors_log.append("➡️ Causa: Limite de taxa da API ORS excedido.")
            ORS_CLIENT_VALID = False 
            st.error("ORS: Limite de requisições da API atingido. Distância desabilitada nesta sessão.")
        return None
    except Exception as e:
        st.session_state.ors_log.append(f"❌ ORS Unexpected Error (geocoding '{nome_lugar}'): {e}")
        return None

@st.cache_data(show_spinner=False) # Cache para a rota completa
def calcular_rota_e_distancia_ors_cached(_client_repr, nome_origem_str, nome_destino_str):
    # _client_repr é uma representação simples do cliente para o cache, como a chave API
    # O cliente real (ors_client) será usado dentro se for válido
    global ORS_CLIENT_VALID, ors_client # Necessário para modificar ORS_CLIENT_VALID
    
    # Reinicializa o log para esta chamada em cache
    # Usar st.session_state aqui dentro de função cacheada pode ser problemático para logs
    # O log será gerenciado fora e passado para exibição
    temp_ors_log = [f"Iniciando cálculo de rota ORS (cacheado): '{nome_origem_str}' -> '{nome_destino_str}'"]
    
    if not ORS_CLIENT_VALID or not ors_client:
        temp_ors_log.append("⚠️ ORS: Cliente não válido para cálculo de rota.")
        return None, None, None, None, temp_ors_log

    coords_origem = obter_coordenadas_ors(nome_origem_str, ors_client) # Usa o ors_client global
    if not ORS_CLIENT_VALID: return None, coords_origem, None, None, st.session_state.ors_log # Retorna log atualizado
    
    coords_destino = obter_coordenadas_ors(nome_destino_str, ors_client)
    if not ORS_CLIENT_VALID: return None, coords_origem, coords_destino, None, st.session_state.ors_log

    if coords_origem and coords_destino:
        try:
            temp_ors_log.append(f" Tentando obter rota entre {coords_origem} e {coords_destino}...")
            # Usa o ors_client global
            rota_result = ors_client.directions(
                coordinates=[coords_origem, coords_destino],
                profile="driving-car", format="geojson", geometry="true"
            )
            if rota_result and rota_result.get('features'):
                feature = rota_result['features'][0]
                distancia_metros = feature['properties']['segments'][0]['distance']
                distancia_km = distancia_metros / 1000
                route_geometry = feature['geometry']['coordinates'] 
                temp_ors_log.append(f"✔️ ORS: Distância: {distancia_km:.2f} km. Geometria da rota obtida.")
                # Atualiza o log principal da sessão com os logs desta função cacheada
                st.session_state.ors_log.extend(temp_ors_log)
                return distancia_km, coords_origem, coords_destino, route_geometry
            else:
                temp_ors_log.append(f"❌ ORS Error: Resposta da rota inesperada ou vazia.")
                st.session_state.ors_log.extend(temp_ors_log)
                return None, coords_origem, coords_destino, None
        except ors_exceptions.ApiError as e:
            http_status = getattr(e, 'http_status', None) or getattr(e, 'status_code', None)
            temp_ors_log.append(f"❌ ORS API Error (routing): HTTP {http_status if http_status else 'N/A'} - {e}")
            if http_status == 429:
                temp_ors_log.append("➡️ Causa: Limite de taxa da API ORS excedido.")
                ORS_CLIENT_VALID = False
                st.error("ORS: Limite de requisições da API atingido. Distância desabilitada.")
            st.session_state.ors_log.extend(temp_ors_log)
            return None, coords_origem, coords_destino, None
        except Exception as e:
            temp_ors_log.append(f"❌ ORS Error (processando resposta da rota): {e}")
            st.session_state.ors_log.extend(temp_ors_log)
            return None, coords_origem, coords_destino, None
    else:
        temp_ors_log.append("⚠️ ORS: Rota não calculada (origem ou destino não geocodificado).")
        st.session_state.ors_log.extend(temp_ors_log)
        return None, coords_origem, coords_destino, None
# ----- FIM DAS DEFINIÇÕES DE DADOS E FUNÇÕES -----

st.set_page_config(layout="wide", page_title="Calculadora de Frete ANTT")
st.title("Cálculo de Frete ANTT e Distância 🚚")
st.markdown("Insira os dados para consultar o frete e a distância.")

if not ORS_CLIENT_VALID and ORS_API_KEY and ORS_API_KEY != "SUA_CHAVE_API_AQUI": # Avisa se o cliente falhou mas uma chave foi provida
    st.error("Cliente OpenRouteService não pôde ser inicializado. Verifique sua chave API ORS nos Secrets ou os logs para erros de limite de taxa. Funcionalidade de distância e mapa estarão desabilitadas.")
elif not ORS_API_KEY or ORS_API_KEY == "SUA_CHAVE_API_AQUI":
     st.warning("Chave da API OpenRouteService (ORS_API_KEY) não configurada nos secrets do Streamlit Cloud. A funcionalidade de cálculo de distância via ORS e o mapa estarão desabilitados.")


if 'ors_log' not in st.session_state: st.session_state.ors_log = []
if 'map_data' not in st.session_state: 
    st.session_state.map_data = {'points_df': None, 'route_df': None}

# --- Inputs do Usuário ---
data_selecionada_dt_widget = st.date_input(
    "🗓️ Data da requisição:", 
    datetime.now(), 
    help="Selecione a data para o cálculo dos componentes ANTT."
)
if data_selecionada_dt_widget:
    data_para_calculo_antt_str = data_selecionada_dt_widget.strftime('%d/%m/%Y')
    st.caption(f"Formato para componentes ANTT: **{data_para_calculo_antt_str}**")
else:
    data_para_calculo_antt_str = datetime.now().strftime('%d/%m/%Y') # Fallback


# --- Exibição Reativa dos Componentes ANTT Base ---
if data_para_calculo_antt_str:
    normativo_reativo, frete_componentes_reativo, data_obj_reativo = encontrar_frete_vigente(tabela_antt, data_para_calculo_antt_str)
    
    st.markdown("---")
    st.markdown("##### 📜 Componentes Base (ANTT) para a Data Selecionada:")
    if data_obj_reativo is None: # Checa se parse da data falhou em encontrar_frete_vigente
        st.warning("Formato de data inválido para buscar taxas ANTT.")
    elif normativo_reativo and frete_componentes_reativo:
        coef_desloc_antt_reativo = frete_componentes_reativo[0]
        valor_fixo_cd_antt_reativo = frete_componentes_reativo[1]
        st.info(f"**Normativo ANTT Aplicável:** {normativo_reativo}")
        r_col1, r_col2 = st.columns(2)
        r_col1.metric("R$ / km (Base ANTT)", f"{coef_desloc_antt_reativo:.3f}")
        r_col2.metric("Valor Fixo Carga/Descarga (ANTT)", f"R$ {valor_fixo_cd_antt_reativo:.2f}")
    else:
        st.warning(f"Nenhuma taxa ANTT encontrada para a data: {data_para_calculo_antt_str}")
    st.markdown("---")

# --- Formulário para o restante dos inputs e cálculo principal ---
with st.form(key="main_calculation_form"):
    st.markdown("##### 🌍 Localidades (para cálculo de distância via ORS)")
    origem_form = st.text_input("Local de Origem:", value="Fortaleza, CE, Brasil")
    destino_form = st.text_input("Local de Destino:", value="São Paulo, SP, Brasil")

    st.markdown("##### 💰 Adicionais Personalizados")
    col_adic1_form, col_adic2_form = st.columns(2)
    with col_adic1_form:
        valor_dificuldade_form = st.number_input("Valor por Dificuldade (R$):", 
                                            min_value=0.0, value=0.0, format="%.2f")
    with col_adic2_form:
        adicional_desloc_taxa_form = st.number_input("Adicional por deslocamento (R$/km):", 
                                                      min_value=0.0, value=0.0, format="%.3f")
    
    submit_button_form = st.form_submit_button("Calcular Rota e Frete Completo 🧮", disabled=not ORS_CLIENT_VALID)

if submit_button_form:
    # Usa a data já formatada e os componentes ANTT reativos para o cálculo final
    data_final_str = data_para_calculo_antt_str 
    normativo_final, frete_comp_final, data_obj_final = normativo_reativo, frete_componentes_reativo, data_obj_reativo

    if not origem_form.strip() or not destino_form.strip():
        st.error("Por favor, preencha os nomes dos locais de origem e destino no formulário.")
    elif not ORS_CLIENT_VALID:
        st.error("Cliente ORS não está válido. Verifique a chave API ou mensagens de erro.")
    else:
        with st.spinner("Calculando rota e frete completo... ⏳"):
            # Passa uma string simples para o cache para representar o cliente ORS
            # já que o objeto cliente em si não é diretamente hasheável pelo st.cache_data
            # A função cacheada usará o cliente global 'ors_client'
            client_repr_for_cache = ORS_API_KEY if ORS_API_KEY else "no_key"
            
            # Limpa o log da sessão ANTES de chamar a função que irá popular ele
            st.session_state.ors_log = [] 
            
            distancia, coords_o, coords_d, route_geom = calcular_rota_e_distancia_ors_cached(
                client_repr_for_cache, origem_form, destino_form
            )
            
            map_points_list = []
            if coords_o: map_points_list.append({'latitude': coords_o[1], 'longitude': coords_o[0], 'tipo': 'Origem', 'cor': [200, 30, 0, 200]})
            if coords_d: map_points_list.append({'latitude': coords_d[1], 'longitude': coords_d[0], 'tipo': 'Destino', 'cor': [0, 0, 255, 200]})
            
            st.session_state.map_data['points_df'] = pd.DataFrame(map_points_list) if map_points_list else None
            st.session_state.map_data['route_df'] = [{"path": route_geom, "name": f"Rota: {origem_form} para {destino_form}"}] if route_geom else None

            # Exibição dos Resultados
            st.markdown("---") 
            st.subheader("📊 RESULTADOS DO CÁLCULO FINAL")
            # ... (exibição das informações de data, origem, destino e distância como antes)
            res_col1, res_col2 = st.columns(2)
            with res_col1:
                st.markdown(f"**Data da Requisição:** `{data_final_str}`")
                st.markdown(f"**Origem Informada:** `{origem_form}`")
            with res_col2:
                st.markdown(f"**Destino Informado:** `{destino_form}`")
                if distancia is not None:
                    st.metric(label="Distância Calculada (ORS)", value=f"{distancia:.2f} km")
                else:
                    st.error("Distância não pôde ser calculada via ORS.")
            st.markdown("---")


            if data_obj_final is None:
                st.error("ERRO: Formato de data inválido na data submetida.")
            elif normativo_final and frete_comp_final:
                coef_desloc_antt = frete_comp_final[0]
                valor_fixo_cd_antt = frete_comp_final[1]

                # Exibe os componentes ANTT usados no cálculo final (já mostrados reativamente, mas bom confirmar)
                st.markdown("#### 📜 Componentes ANTT Utilizados no Cálculo Final")
                st.info(f"**Normativo:** {normativo_final} | **R$/km Base:** {coef_desloc_antt:.3f} | **C/D Fixo:** R$ {valor_fixo_cd_antt:.2f}")

                if distancia is not None and distancia > 0:
                    custo_deslocamento_antt = coef_desloc_antt * distancia
                    custo_adicional_desloc = adicional_desloc_taxa_form * distancia
                    frete_total_calculado = (custo_deslocamento_antt + valor_fixo_cd_antt + 
                                             custo_adicional_desloc + valor_dificuldade_form)
                    frete_real_por_km = frete_total_calculado / distancia
                    delta_vs_base = frete_real_por_km - coef_desloc_antt
                    percent_change = (delta_vs_base / coef_desloc_antt * 100) if coef_desloc_antt != 0 else 0
                    
                    delta_color = "off" 
                    arrow = "➖" # Neutro
                    if delta_vs_base > 0.001: delta_color = "normal"; arrow = "⬆️"
                    elif delta_vs_base < -0.001: delta_color = "inverse"; arrow = "⬇️"

                    st.markdown("#### 💰 Detalhamento dos Custos do Frete")
                    det_cols = st.columns(4) # Origem ANTT, Adic. Desloc, Dificuldade, C/D ANTT
                    det_cols[0].metric("Custo Desloc. (ANTT)", f"R$ {custo_deslocamento_antt:.2f}")
                    det_cols[1].metric("Custo Adic. Desloc.", f"R$ {custo_adicional_desloc:.2f}", help=f"{adicional_desloc_taxa_form:.3f} R$/km")
                    det_cols[2].metric("Valor por Dificuldade", f"R$ {valor_dificuldade_form:.2f}")
                    det_cols[3].metric("Carga/Descarga (ANTT)", f"R$ {valor_fixo_cd_antt:.2f}")
                                    
                    st.markdown("---")
                    st.subheader("🏁 Estimativas Finais do Frete")
                    final_col1, final_col2 = st.columns(2)
                    final_col1.metric("Valor Total Final Estimado", f"R$ {frete_total_calculado:.2f}")
                    final_col2.metric(label=f"Frete Real (R$/km Total) {arrow}", 
                                      value=f"R$ {frete_real_por_km:.3f}",
                                      delta=f"{percent_change:.1f}% vs Base ANTT", 
                                      delta_color=delta_color)
                elif distancia == 0:
                    st.warning("Distância é 0 km. Calculando apenas custos fixos.")
                    custos_fixos_total = valor_fixo_cd_antt + valor_dificuldade_form
                    st.metric("Valor Total Estimado (Custos Fixos)", f"R$ {custos_fixos_total:.2f}")
                else: 
                    st.warning("Sem distância, não é possível calcular custos variáveis ou 'Frete Real'.")
            elif not (data_obj_final is None): 
                st.warning(f"Nenhuma tabela de frete ANTT para a data {data_final_str}.")
            
            # --- Exibição do Mapa ---
            st.markdown("---")
            st.subheader("🗺️ Mapa da Rota Estimada")
            map_df = st.session_state.map_data.get('points_df')
            route_data_for_map = st.session_state.map_data.get('route_df')

            if map_df is not None and not map_df.empty:
                center_lat = map_df['latitude'].mean()
                center_lon = map_df['longitude'].mean()
                initial_zoom = 3 if (distancia and distancia > 1000) else 5 if (distancia and distancia > 100) else 8

                layers_for_map = []
                # Camada de Pontos
                layers_for_map.append(pdk.Layer(
                    'ScatterplotLayer', data=map_df, get_position='[longitude, latitude]',
                    get_fill_color='cor', get_radius=20000, pickable=True,
                    tooltip={"html": "<b>{tipo}</b><br/>Lat: {latitude}<br/>Lon: {longitude}"}
                ))
                # Camada da Rota
                if PYDECK_AVAILABLE and pdk is not None and route_data_for_map:
                    layers_for_map.append(pdk.Layer(
                        "PathLayer", data=route_data_for_map, get_path="path", get_width=15, 
                        get_color=[20, 100, 230, 180], width_min_pixels=2, pickable=True,
                        tooltip={"html": "<b>{name}</b>"}
                    ))
                
                if PYDECK_AVAILABLE and pdk is not None:
                    try:
                        st.pydeck_chart(pdk.Deck(
                            map_style='mapbox://styles/mapbox/outdoors-v11', # Estilo de mapa
                            initial_view_state=pdk.ViewState(
                                latitude=center_lat, longitude=center_lon, 
                                zoom=initial_zoom, pitch=45, bearing=0
                            ),
                            layers=layers_for_map,
                            tooltip=True # Tooltip padrão do Pydeck
                        ))
                    except Exception as e_map:
                        st.error(f"Erro ao gerar mapa Pydeck: {e_map}. Usando st.map.")
                        if not map_df.empty: st.map(map_df, zoom=initial_zoom)
                elif not map_df.empty: 
                    st.map(map_df, zoom=initial_zoom)
            else:
                st.caption("Coordenadas não disponíveis para o mapa.")

            # Exibir logs do ORS
            with st.expander("🔍 Ver Log de Processamento OpenRouteService", expanded=False):
                if st.session_state.ors_log:
                    for msg in st.session_state.ors_log:
                        if "✔️" in msg: st.success(msg)
                        elif "⚠️" in msg: st.warning(msg)
                        elif "❌" in msg: st.error(msg)
                        else: st.text(msg)
                else:
                    st.caption("Nenhuma mensagem de log do ORS.")
        elif not ORS_CLIENT_VALID:
            st.error("Cálculo não pode prosseguir: Cliente OpenRouteService não está operacional.")
