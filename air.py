import ee
import folium
from streamlit_folium import st_folium
import streamlit as st
import plotly.express as px
import json
import time
from datetime import datetime

# Xác thực và khởi tạo Earth Engine
ee.Initialize(project='teak-vent-437103-t3')

# Cấu hình bố cục trang
st.set_page_config(layout="wide")

# Tiêu đề chính
st.title("Phân tích chất lượng không khí - Phường Tân Bình, TP Đồng Xoài")

# Chọn năm phân tích
current_year = datetime.now().year
available_years = list(range(2019, current_year + 1))
selected_year = st.sidebar.selectbox(
    "Chọn năm phân tích:",
    available_years,
    index=available_years.index(2023) if 2023 in available_years else 0
)

@st.cache_data(ttl=3600)  # Cache dữ liệu trong 1 giờ
def load_data(year):
    # Tải FeatureCollection tanbinh và chỉ lấy hình học để giảm kích thước
    tanbinh = ee.FeatureCollection("projects/teak-vent-437103-t3/assets/tanbinh").geometry()
    
    # Tạo khoảng thời gian cho năm được chọn
    start_date = f"{year}-01-01"
    end_date = f"{year}-12-31"
    
    # Load CO data
    ST5_CO = ee.ImageCollection('COPERNICUS/S5P/OFFL/L3_CO')
    image_CO = ST5_CO.filterBounds(tanbinh) \
                     .select('CO_column_number_density') \
                     .filterDate(start_date, end_date) \
                     .mean() \
                     .clip(tanbinh)
    map_id_dict_CO = image_CO.getMapId({
        'min': 0,
        'max': 0.05,
        'palette': ['black', 'blue', 'purple', 'cyan', 'green', 'yellow', 'red']
    })
    
    # Load NO2 data
    ST5_NO2 = ee.ImageCollection('COPERNICUS/S5P/OFFL/L3_NO2')
    image_NO2 = ST5_NO2.filterBounds(tanbinh) \
                     .select('tropospheric_NO2_column_number_density') \
                     .filterDate(start_date, end_date) \
                     .mean() \
                     .clip(tanbinh)
    map_id_dict_NO2 = image_NO2.getMapId({
        'min': 0,
        'max': 0.0002,
        'palette': ['black', 'blue', 'purple', 'cyan', 'green', 'yellow', 'red']
    })
    
    # Load HCHO data
    ST5_HCHO = ee.ImageCollection('COPERNICUS/S5P/OFFL/L3_HCHO')
    image_HCHO = ST5_HCHO.filterBounds(tanbinh) \
                     .select('tropospheric_HCHO_column_number_density') \
                     .filterDate(start_date, end_date) \
                     .mean() \
                     .clip(tanbinh)
    map_id_dict_HCHO = image_HCHO.getMapId({
        'min': 0.0,
        'max': 0.0003,
        'palette': ['black', 'blue', 'purple', 'cyan', 'green', 'yellow', 'red']
    })
    
    return tanbinh, map_id_dict_CO, image_CO, map_id_dict_NO2, image_NO2, map_id_dict_HCHO, image_HCHO

# Hiển thị thanh tiến trình khi đang tải dữ liệu
with st.spinner(f'Đang tải dữ liệu từ Google Earth Engine cho năm {selected_year}...'):
    tanbinh, map_id_dict_CO, image_CO, map_id_dict_NO2, image_NO2, map_id_dict_HCHO, image_HCHO = load_data(selected_year)

# Chia layout thành hai cột: bản đồ bên trái, thông tin bên phải
col_map, col_info = st.columns([3, 2])

with col_map:
    # Tạo bản đồ với folium - Tọa độ cho phường Tân Bình, TP Đồng Xoài, Bình Phước
    m = folium.Map(location=[11.525284855216535, 106.89144522904412], zoom_start=14)

    # Thêm lớp CO vào bản đồ
    folium.TileLayer(
        tiles=map_id_dict_CO['tile_fetcher'].url_format,
        attr='Google Earth Engine',
        overlay=True,
        name='S5P CO',
        show=True
    ).add_to(m)

    # Thêm lớp NO2 vào bản đồ
    folium.TileLayer(
        tiles=map_id_dict_NO2['tile_fetcher'].url_format,
        attr='Google Earth Engine',
        overlay=True,
        name='S5P NO2',
        show=True
    ).add_to(m)

    # Thêm lớp HCHO vào bản đồ
    folium.TileLayer(
        tiles=map_id_dict_HCHO['tile_fetcher'].url_format,
        attr='Google Earth Engine',
        overlay=True,
        name='S5P HCHO',
        show=True
    ).add_to(m)

    # Thêm lớp FeatureCollection vào bản đồ
    try:
        # Sử dụng cách an toàn để lấy GeoJSON từ geometry
        tanbinh_geojson = tanbinh.getInfo()
        folium.GeoJson(
            tanbinh_geojson,
            name='Phường Tân Bình',
            show=False
        ).add_to(m)
    except Exception as e:
        st.warning(f"Không thể hiển thị ranh giới Phường Tân Bình: {str(e)}")

    # Thêm công cụ vẽ
    draw = folium.plugins.Draw(export=True)
    m.add_child(draw)

    # Thêm chú thích cho bản đồ
    folium.LayerControl().add_to(m)

    st.write(f"👉 Click vào bản đồ để xem nồng độ khí tại vị trí đó (Dữ liệu năm {selected_year})")
    
    # Hiển thị bản đồ và lấy dữ liệu tương tác
    st_data = st_folium(m, width=800, height=600)

with col_info:
    # Chứa thông tin kết quả phân tích
    st.subheader(f"Thông tin phân tích (Năm {selected_year})")
    
    # Caching cho sample point data
    @st.cache_data(ttl=3600)  # Cache 1 giờ
    def get_point_data(lng, lat, year):
        clicked_point = ee.Geometry.Point([lng, lat])
        
        # Lấy giá trị CO, NO2, HCHO cùng lúc
        co_value = image_CO.sample(region=clicked_point, scale=1000, geometries=True).first().get('CO_column_number_density').getInfo()
        no2_value = image_NO2.sample(region=clicked_point, scale=1000, geometries=True).first().get('tropospheric_NO2_column_number_density').getInfo()
        hcho_value = image_HCHO.sample(region=clicked_point, scale=1000, geometries=True).first().get('tropospheric_HCHO_column_number_density').getInfo()
        
        return co_value, no2_value, hcho_value
    
    # Kiểm tra nếu người dùng click vào bản đồ
    if st_data.get('last_clicked'):
        # Lấy tọa độ của điểm đã click
        clicked_lat = st_data['last_clicked']['lat']
        clicked_lng = st_data['last_clicked']['lng']
        
        # Hiển thị phần tiêu đề kết quả
        st.markdown(f"#### 📌 Nồng độ khí tại vị trí đã chọn")
        st.markdown(f"**Tọa độ**: {clicked_lat:.4f}, {clicked_lng:.4f}")
        
        # Hiển thị thanh tiến trình cho việc lấy dữ liệu điểm
        with st.spinner('Đang phân tích dữ liệu...'):
            co_value, no2_value, hcho_value = get_point_data(clicked_lng, clicked_lat, selected_year)
        
        # Hiển thị kết quả
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(
                label="CO (mol/m²)",
                value=f"{co_value:.6f}" if co_value is not None else "Không có dữ liệu",
                delta=None
            )
        with col2:
            st.metric(
                label="NO2 (mol/m²)",
                value=f"{no2_value:.6f}" if no2_value is not None else "Không có dữ liệu",
                delta=None
            )
        with col3:
            st.metric(
                label="HCHO (mol/m²)",
                value=f"{hcho_value:.6f}" if hcho_value is not None else "Không có dữ liệu",
                delta=None
            )
    
    # Hiển thị thông tin khu vực được vẽ
    if st_data['last_active_drawing'] is not None:
        st.markdown("---")
        st.markdown("#### 📍 Phân tích khu vực được chọn")
        
        # Cache cho việc phân tích vùng
        @st.cache_data(ttl=3600)
        def analyze_region(geojson_str, year):
            drawn_geojson = json.loads(geojson_str)
            drawn_feature = ee.Feature(ee.Geometry(drawn_geojson))
            
            # Phân tích CO
            selected_image_co = image_CO.clip(drawn_feature.geometry())
            mean_co = selected_image_co.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=drawn_feature.geometry(),
                scale=1000,
                maxPixels=1e13
            ).getInfo()
            mean_co_value = mean_co.get('CO_column_number_density', 'Không có dữ liệu')
            
            # Phân tích NO2
            selected_image_no2 = image_NO2.clip(drawn_feature.geometry())
            mean_no2 = selected_image_no2.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=drawn_feature.geometry(),
                scale=1000,
                maxPixels=1e13
            ).getInfo()
            mean_no2_value = mean_no2.get('tropospheric_NO2_column_number_density', 'Không có dữ liệu')
            
            # Phân tích HCHO
            selected_image_hcho = image_HCHO.clip(drawn_feature.geometry())
            mean_hcho = selected_image_hcho.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=drawn_feature.geometry(),
                scale=1000,
                maxPixels=1e13
            ).getInfo()
            mean_hcho_value = mean_hcho.get('tropospheric_HCHO_column_number_density', 'Không có dữ liệu')
            
            return mean_co_value, mean_no2_value, mean_hcho_value
        
        # Chuyển geojson sang chuỗi để có thể cache
        geojson_str = json.dumps(st_data['last_active_drawing']['geometry'])
        
        # Hiển thị tiến trình khi phân tích khu vực
        with st.spinner('Đang phân tích khu vực được chọn...'):
            mean_co_value, mean_no2_value, mean_hcho_value = analyze_region(geojson_str, selected_year)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(
                label="CO (mol/m²)", 
                value=f"{mean_co_value:.6f}" if isinstance(mean_co_value, float) else mean_co_value,
                delta=None
            )
        with col2:
            st.metric(
                label="NO2 (mol/m²)", 
                value=f"{mean_no2_value:.6f}" if isinstance(mean_no2_value, float) else mean_no2_value,
                delta=None
            )
        with col3:
            st.metric(
                label="HCHO (mol/m²)", 
                value=f"{mean_hcho_value:.6f}" if isinstance(mean_hcho_value, float) else mean_hcho_value,
                delta=None
            )
    
    # Thêm giải thích cho người dùng
    st.markdown("---")
    st.markdown("### Hướng dẫn sử dụng")
    st.markdown(f"""
    - **Chọn năm**: Sử dụng thanh bên trái để chọn năm phân tích (2019-{current_year})
    - **Click vào bản đồ**: Hiển thị giá trị nồng độ khí tại điểm đó
    - **Sử dụng công cụ vẽ**: Vẽ một khu vực để phân tích giá trị trung bình
    - **Chuyển đổi lớp**: Sử dụng bảng điều khiển lớp ở góc phải bản đồ để chuyển đổi giữa các loại khí
    """)

# Tính giá trị trung bình theo tháng cho năm được chọn
@st.cache_data(ttl=43200)  # Lưu cache 12 giờ
def monthly_mean(year, collection_name, band_name, _geometry):
    months = ee.List.sequence(1, 12)
    collection = ee.ImageCollection(collection_name)

    return ee.FeatureCollection(months.map(lambda month: ee.Feature(None, {
        'month': month,
        'mean': collection.filterBounds(_geometry)
                         .filterDate(ee.Date.fromYMD(year, month, 1), ee.Date.fromYMD(year, month, 1).advance(1, 'month'))
                         .select(band_name)
                         .mean()
                         .reduceRegion(
                             reducer=ee.Reducer.mean(),
                             geometry=_geometry,
                             scale=1000,
                             maxPixels=1e13
                         ).get(band_name)
    })))

# Tạo các biểu đồ trung bình theo tháng (với cache)
with st.spinner(f'Đang tạo biểu đồ theo tháng cho năm {selected_year}...'):
    monthly_means_co = monthly_mean(selected_year, 'COPERNICUS/S5P/OFFL/L3_CO', 'CO_column_number_density', tanbinh).getInfo()
    monthly_means_no2 = monthly_mean(selected_year, 'COPERNICUS/S5P/OFFL/L3_NO2', 'tropospheric_NO2_column_number_density', tanbinh).getInfo()
    monthly_means_hcho = monthly_mean(selected_year, 'COPERNICUS/S5P/OFFL/L3_HCHO', 'tropospheric_HCHO_column_number_density', tanbinh).getInfo()

# Tab để hiển thị các biểu đồ
tab1, tab2, tab3 = st.tabs(["Nồng độ CO", "Nồng độ NO2", "Nồng độ HCHO"])

with tab1:
    # CO Chart
    months = [feature['properties']['month'] for feature in monthly_means_co['features']]
    mean_co_values = [feature['properties']['mean'] for feature in monthly_means_co['features']]
    fig_co = px.line(x=months, y=mean_co_values, labels={'x': 'Tháng', 'y': 'Giá trị CO (mol/m^2)'}, 
                    title=f'Giá trị trung bình CO theo tháng năm {selected_year} tại Phường Tân Bình, TP Đồng Xoài')
    st.plotly_chart(fig_co, use_container_width=True)

with tab2:
    # NO2 Chart
    mean_no2_values = [feature['properties']['mean'] for feature in monthly_means_no2['features']]
    fig_no2 = px.line(x=months, y=mean_no2_values, labels={'x': 'Tháng', 'y': 'Giá trị NO2 (mol/m^2)'}, 
                    title=f'Giá trị trung bình NO2 theo tháng năm {selected_year} tại Phường Tân Bình, TP Đồng Xoài')
    st.plotly_chart(fig_no2, use_container_width=True)

with tab3:
    # HCHO Chart
    mean_hcho_values = [feature['properties']['mean'] for feature in monthly_means_hcho['features']]
    fig_hcho = px.line(x=months, y=mean_hcho_values, labels={'x': 'Tháng', 'y': 'Giá trị HCHO (mol/m^2)'}, 
                     title=f'Giá trị trung bình HCHO theo tháng năm {selected_year} tại Phường Tân Bình, TP Đồng Xoài')
    st.plotly_chart(fig_hcho, use_container_width=True)

# Thêm so sánh giữa các năm nếu người dùng muốn
if st.sidebar.checkbox("Hiển thị so sánh giữa các năm", value=False):
    st.sidebar.markdown("### Chọn loại khí để so sánh")
    gas_type = st.sidebar.radio(
        "Loại khí:",
        ["CO", "NO2", "HCHO"]
    )
    
    # Chọn các năm để so sánh
    years_to_compare = st.sidebar.multiselect(
        "Chọn các năm để so sánh:",
        available_years,
        default=[selected_year]
    )
    
    if years_to_compare:
        st.markdown("## So sánh nồng độ khí giữa các năm")
        
        with st.spinner('Đang tạo biểu đồ so sánh...'):
            # Dữ liệu cho biểu đồ so sánh
            comparison_data = []
            
            for year in years_to_compare:
                if gas_type == "CO":
                    monthly_data = monthly_mean(year, 'COPERNICUS/S5P/OFFL/L3_CO', 'CO_column_number_density', tanbinh).getInfo()
                    for feature in monthly_data['features']:
                        comparison_data.append({
                            "Năm": str(year),
                            "Tháng": feature['properties']['month'],
                            "Giá trị": feature['properties']['mean']
                        })
                elif gas_type == "NO2":
                    monthly_data = monthly_mean(year, 'COPERNICUS/S5P/OFFL/L3_NO2', 'tropospheric_NO2_column_number_density', tanbinh).getInfo()
                    for feature in monthly_data['features']:
                        comparison_data.append({
                            "Năm": str(year),
                            "Tháng": feature['properties']['month'],
                            "Giá trị": feature['properties']['mean']
                        })
                else:  # HCHO
                    monthly_data = monthly_mean(year, 'COPERNICUS/S5P/OFFL/L3_HCHO', 'tropospheric_HCHO_column_number_density', tanbinh).getInfo()
                    for feature in monthly_data['features']:
                        comparison_data.append({
                            "Năm": str(year),
                            "Tháng": feature['properties']['month'],
                            "Giá trị": feature['properties']['mean']
                        })
            
            # Tạo DataFrame từ dữ liệu so sánh
            import pandas as pd
            df_comparison = pd.DataFrame(comparison_data)
            
            # Vẽ biểu đồ so sánh
            fig_comparison = px.line(
                df_comparison, 
                x="Tháng", 
                y="Giá trị", 
                color="Năm",
                labels={"Giá trị": f"Giá trị {gas_type} (mol/m^2)"},
                title=f'So sánh nồng độ {gas_type} giữa các năm tại Phường Tân Bình, TP Đồng Xoài'
            )
            
            st.plotly_chart(fig_comparison, use_container_width=True)
            
            # Hiển thị bảng dữ liệu
            if st.checkbox("Hiển thị bảng dữ liệu"):
                st.dataframe(df_comparison)
