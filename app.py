from flask import Flask, render_template, jsonify, request
import ee
import json
import plotly
import plotly.express as px
import os
from datetime import datetime

app = Flask(__name__)

# Xác thực và khởi tạo Earth Engine
ee.Initialize(project='teak-vent-437103-t3')

# Cache cho dữ liệu
_cache = {}

def load_data(year=2023):
    # Kiểm tra nếu đã có trong cache
    cache_key = f"data_{year}"
    if cache_key in _cache:
        return _cache[cache_key]
    
    # Tạo khoảng thời gian cho năm được chọn
    start_date = f"{year}-01-01"
    end_date = f"{year}-12-31"
    
    # Tải FeatureCollection tanbinh và chỉ lấy hình học để giảm kích thước
    tanbinh = ee.FeatureCollection("projects/teak-vent-437103-t3/assets/tanbinh").geometry()
    
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
    
    # Cache lại dữ liệu
    data = {
        'tanbinh': tanbinh,
        'map_id_dict_CO': map_id_dict_CO,
        'image_CO': image_CO,
        'map_id_dict_NO2': map_id_dict_NO2,
        'image_NO2': image_NO2,
        'map_id_dict_HCHO': map_id_dict_HCHO,
        'image_HCHO': image_HCHO,
        'tanbinh_geojson': tanbinh.getInfo()
    }
    _cache[cache_key] = data
    
    return data

def get_point_data(lng, lat, data):
    clicked_point = ee.Geometry.Point([lng, lat])
    
    # Lấy giá trị CO, NO2, HCHO cùng lúc
    co_value = data['image_CO'].sample(region=clicked_point, scale=1000, geometries=True).first().get('CO_column_number_density').getInfo()
    no2_value = data['image_NO2'].sample(region=clicked_point, scale=1000, geometries=True).first().get('tropospheric_NO2_column_number_density').getInfo()
    hcho_value = data['image_HCHO'].sample(region=clicked_point, scale=1000, geometries=True).first().get('tropospheric_HCHO_column_number_density').getInfo()
    
    return co_value, no2_value, hcho_value

def analyze_region(geojson_str, data):
    drawn_geojson = json.loads(geojson_str)
    drawn_feature = ee.Feature(ee.Geometry(drawn_geojson))
    
    # Phân tích CO
    selected_image_co = data['image_CO'].clip(drawn_feature.geometry())
    mean_co = selected_image_co.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=drawn_feature.geometry(),
        scale=1000,
        maxPixels=1e13
    ).getInfo()
    mean_co_value = mean_co.get('CO_column_number_density', 'Không có dữ liệu')
    
    # Phân tích NO2
    selected_image_no2 = data['image_NO2'].clip(drawn_feature.geometry())
    mean_no2 = selected_image_no2.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=drawn_feature.geometry(),
        scale=1000,
        maxPixels=1e13
    ).getInfo()
    mean_no2_value = mean_no2.get('tropospheric_NO2_column_number_density', 'Không có dữ liệu')
    
    # Phân tích HCHO
    selected_image_hcho = data['image_HCHO'].clip(drawn_feature.geometry())
    mean_hcho = selected_image_hcho.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=drawn_feature.geometry(),
        scale=1000,
        maxPixels=1e13
    ).getInfo()
    mean_hcho_value = mean_hcho.get('tropospheric_HCHO_column_number_density', 'Không có dữ liệu')
    
    return mean_co_value, mean_no2_value, mean_hcho_value

def monthly_mean(year, collection_name, band_name, _geometry):
    # Kiểm tra nếu đã có trong cache
    cache_key = f"{year}_{collection_name}_{band_name}"
    if cache_key in _cache:
        return _cache[cache_key]
    
    months = ee.List.sequence(1, 12)
    collection = ee.ImageCollection(collection_name)

    result = ee.FeatureCollection(months.map(lambda month: ee.Feature(None, {
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
    }))).getInfo()
    
    # Cache lại dữ liệu
    _cache[cache_key] = result
    
    return result

@app.route('/')
def index():
    # Lấy năm từ request, mặc định là 2023
    year = request.args.get('year', default=2023, type=int)
    
    # Tạo danh sách các năm có sẵn
    current_year = datetime.now().year
    available_years = list(range(2019, current_year + 1))
    
    # Tải dữ liệu cho năm được chọn
    data = load_data(year)
    
    # Chuẩn bị dữ liệu để truyền vào template
    mapData = {
        'center': [11.5353, 106.8799],
        'zoom': 14,
        'co_tiles': data['map_id_dict_CO']['tile_fetcher'].url_format,
        'no2_tiles': data['map_id_dict_NO2']['tile_fetcher'].url_format,
        'hcho_tiles': data['map_id_dict_HCHO']['tile_fetcher'].url_format,
        'tanbinh_geojson': data['tanbinh_geojson'],
        'selected_year': year
    }
    
    return render_template('index.html', mapData=mapData, available_years=available_years)

@app.route('/api/point_data', methods=['POST'])
def point_data_api():
    # Lấy năm từ request
    req_data = request.json
    year = req_data.get('year', 2023)
    lng = req_data.get('lng')
    lat = req_data.get('lat')
    
    # Tải dữ liệu cho năm được chọn
    data = load_data(year)
    
    # Lấy dữ liệu
    co_value, no2_value, hcho_value = get_point_data(lng, lat, data)
    
    return jsonify({
        'co_value': co_value,
        'no2_value': no2_value,
        'hcho_value': hcho_value
    })

@app.route('/api/region_data', methods=['POST'])
def region_data_api():
    # Lấy năm từ request
    req_data = request.json
    year = req_data.get('year', 2023)
    geojson_str = json.dumps(req_data.get('geometry'))
    
    # Tải dữ liệu cho năm được chọn
    data = load_data(year)
    
    # Phân tích khu vực
    mean_co_value, mean_no2_value, mean_hcho_value = analyze_region(geojson_str, data)
    
    return jsonify({
        'mean_co_value': mean_co_value,
        'mean_no2_value': mean_no2_value,
        'mean_hcho_value': mean_hcho_value
    })

@app.route('/api/monthly_data')
def monthly_data_api():
    # Lấy năm từ request
    year = request.args.get('year', default=2023, type=int)
    
    # Tải dữ liệu cho năm được chọn
    data = load_data(year)
    
    # Lấy dữ liệu theo tháng
    monthly_means_co = monthly_mean(year, 'COPERNICUS/S5P/OFFL/L3_CO', 'CO_column_number_density', data['tanbinh'])
    monthly_means_no2 = monthly_mean(year, 'COPERNICUS/S5P/OFFL/L3_NO2', 'tropospheric_NO2_column_number_density', data['tanbinh'])
    monthly_means_hcho = monthly_mean(year, 'COPERNICUS/S5P/OFFL/L3_HCHO', 'tropospheric_HCHO_column_number_density', data['tanbinh'])
    
    # Xử lý dữ liệu cho biểu đồ
    months = [feature['properties']['month'] for feature in monthly_means_co['features']]
    co_values = [feature['properties']['mean'] for feature in monthly_means_co['features']]
    no2_values = [feature['properties']['mean'] for feature in monthly_means_no2['features']]
    hcho_values = [feature['properties']['mean'] for feature in monthly_means_hcho['features']]
    
    # Tạo biểu đồ với plotly
    fig_co = px.line(x=months, y=co_values, 
                  labels={'x': 'Tháng', 'y': 'Giá trị CO (mol/m^2)'}, 
                  title=f'Giá trị trung bình CO theo tháng năm {year} tại Phường Tân Bình, TP Đồng Xoài')
    
    fig_no2 = px.line(x=months, y=no2_values, 
                    labels={'x': 'Tháng', 'y': 'Giá trị NO2 (mol/m^2)'}, 
                    title=f'Giá trị trung bình NO2 theo tháng năm {year} tại Phường Tân Bình, TP Đồng Xoài')
    
    fig_hcho = px.line(x=months, y=hcho_values, 
                     labels={'x': 'Tháng', 'y': 'Giá trị HCHO (mol/m^2)'}, 
                     title=f'Giá trị trung bình HCHO theo tháng năm {year} tại Phường Tân Bình, TP Đồng Xoài')
    
    return jsonify({
        'co_chart': json.loads(plotly.io.to_json(fig_co)),
        'no2_chart': json.loads(plotly.io.to_json(fig_no2)),
        'hcho_chart': json.loads(plotly.io.to_json(fig_hcho)),
        'months': months,
        'co_values': co_values,
        'no2_values': no2_values,
        'hcho_values': hcho_values
    })

@app.route('/api/comparison_data')
def comparison_data_api():
    # Lấy các năm cần so sánh và loại khí
    years = request.args.getlist('years[]', type=int)
    gas_type = request.args.get('gas_type', default='CO')
    
    if not years:
        years = [2023]  # Mặc định là năm 2023
    
    # Tải dữ liệu tanbinh
    data = load_data(years[0])
    tanbinh = data['tanbinh']
    
    # Dữ liệu cho biểu đồ so sánh
    comparison_data = []
    
    for year in years:
        if gas_type == "CO":
            monthly_data = monthly_mean(year, 'COPERNICUS/S5P/OFFL/L3_CO', 'CO_column_number_density', tanbinh)
            for feature in monthly_data['features']:
                comparison_data.append({
                    "year": str(year),
                    "month": feature['properties']['month'],
                    "value": feature['properties']['mean']
                })
        elif gas_type == "NO2":
            monthly_data = monthly_mean(year, 'COPERNICUS/S5P/OFFL/L3_NO2', 'tropospheric_NO2_column_number_density', tanbinh)
            for feature in monthly_data['features']:
                comparison_data.append({
                    "year": str(year),
                    "month": feature['properties']['month'],
                    "value": feature['properties']['mean']
                })
        else:  # HCHO
            monthly_data = monthly_mean(year, 'COPERNICUS/S5P/OFFL/L3_HCHO', 'tropospheric_HCHO_column_number_density', tanbinh)
            for feature in monthly_data['features']:
                comparison_data.append({
                    "year": str(year),
                    "month": feature['properties']['month'],
                    "value": feature['properties']['mean']
                })
    
    # Tạo biểu đồ so sánh với plotly
    import pandas as pd
    df = pd.DataFrame(comparison_data)
    
    fig_comparison = px.line(
        df, 
        x="month", 
        y="value", 
        color="year",
        labels={
            "month": "Tháng", 
            "value": f"Giá trị {gas_type} (mol/m^2)",
            "year": "Năm"
        },
        title=f'So sánh nồng độ {gas_type} giữa các năm tại Phường Tân Bình, TP Đồng Xoài'
    )
    
    return jsonify({
        'comparison_chart': json.loads(plotly.io.to_json(fig_comparison)),
        'comparison_data': comparison_data
    })

if __name__ == '__main__':
    # Tạo thư mục templates nếu chưa có
    if not os.path.exists('templates'):
        os.makedirs('templates')
    
    app.run(debug=True, port=5000) 