# Runs at http://127.0.0.1:8050/ in your web browser.
from dash import Dash, html, dcc, dash_table
from dash.dependencies import Input, Output, State
from plotly.subplots import make_subplots
import plotly.graph_objects as go
import pandas as pd
import plotly.express as px
import base64
import datetime
import io
from collections import OrderedDict

#For styling app
external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']
app = Dash(__name__,
           external_stylesheets=external_stylesheets,
           suppress_callback_exceptions=True)

LUT = OrderedDict([
    ('Baseline', ["0 - None", "1 - Tachycardia", "2 - Bradycardia", "-", "-"]),
    ('Variability', ["0 - Normal", "1 - Abnormal", "-", "-", "-"]),
    ('Accels.', ["0 - Normal", "1 - Abnormal", "-", "-", "-"]),
    ('Decels.', [
        "0 - None", "1 - Intermittent", "2 - Early / Recurrent",
        "3 - Variable", "4 - Late"
    ]),
    ('FIGO', ["0 - Normal", "1 - Suspicious", "2 - Pathalogical", "-", "-"]),
])
LUT_df = pd.DataFrame(LUT)

#Layout of webpage
app.layout = html.Div(children=[
    html.H1(children='CTG Signal Viewer'),
    dcc.Upload(
        id="upload-data",
        children=html.Div(["Drag and Drop or ",
                           html.A("Select Files")]),
        style={
            "width": "100%",
            "height": "60px",
            "lineHeight": "60px",
            "borderWidth": "1px",
            "borderStyle": "dashed",
            "borderRadius": "5px",
            "textAlign": "center",
            "margin": "10px",
        },
        multiple=True,
    ),
    html.Button("Download Features", id="btn_features"),
    dcc.Download(id="download-features-csv"),
    dcc.Store(id='csv-data'),
    dcc.Store(id='feature-data'),
    html.Div([
        dcc.Checklist(id="feature-selection",
                      options={
                          "Baseline": "Baseline",
                          "Variability": "Variability",
                          "Decelerations": "Decelerations",
                          "Accelerations": "Accelerations"
                      },
                      style={'font-size': 20},
                      labelStyle={
                          "align-items": "center",
                          'background': '#abe2fb',
                          'padding': '0.5rem 1rem',
                          'border-radius': '1.5rem'
                      },
                      inline=True),
    ]),
    html.Div(id="Feature-graph"),
    html.Label("Epoch Number"),
    html.Div([
        dcc.Input(id='epoch-select',
                  type='number',
                  min=0,
                  step=1,
                  value=0,
                  placeholder="Epoch Number")
    ]),
    html.Div(id="CTG-graph"),  #Empty Div for callback for CTG Graph
    html.Div([
        dcc.Slider(id='slider-w',
                   min=1000,
                   max=2500,
                   marks={1000: 'Width'},
                   value=1200)
    ]),
    html.Div([
        dcc.Slider(
            id='slider-h', min=500, max=1500, marks={500: 'Height'}, value=700)
    ]),
    html.Div([
        dash_table.DataTable(
            id='feature-table',
            columns=([
                {
                    'id': 'Epoch',
                    'name': 'Epoch',
                    'type': 'numeric'
                },
                {
                    'id': 'Baseline',
                    'name': 'Baseline',
                    'type': 'numeric'
                },
                {
                    'id': 'Variability',
                    'name': 'Variability',
                    'type': 'numeric'
                },
                {
                    'id': 'Accels.',
                    'name': 'Accels.',
                    'type': 'numeric'
                },
                {
                    'id': 'Decels.',
                    'name': 'Decels.',
                    'type': 'numeric'
                },
                {
                    'id': 'FIGO',
                    'name': 'FIGO',
                    'type': 'numeric'
                },
                {
                    'id': 'Notes',
                    'name': 'Notes'
                },
            ]),
            data=[{
                'Epoch': i,
            } for i in range(20)],
            export_format='csv',
            export_headers='display',
            editable=True,
            page_size=10,
            style_data={
                'whiteSpace': 'normal',
                'heigth': 'auto',
                'lineHeight': '15px',
                'minWidth': '80px',
                'width': '80px',
                'maxWidth': '180px',
            },
            style_cell={'textAlign': 'center'},
        ),
    ]),
    html.Div([
        dash_table.DataTable(
            id='LUT',
            data=LUT_df.to_dict('records'),
            columns=[{
                'id': c,
                'name': c
            } for c in LUT_df.columns],
            style_cell={'textAlign': 'left'},
        )
    ])
])


# Parse Contents Uploaded and save to Store
@app.callback(Output('csv-data', 'data'),
              Input('upload-data', 'contents'),
              State('upload-data', 'filename'),
              prevent_initial_call=True)
def parse_contents(contents, filename):
    if contents:
        content_type, content_string = contents[0].split(',')
        decoded = base64.b64decode(content_string)
        df = pd.read_csv(io.StringIO(decoded.decode('utf-8')))
        return df.to_json(orient='split')


@app.callback(
    Output("download-features-csv", "data"),
    Input("btn_csv", "n_clicks"),
    Input("feature-data", "data"),
    prevent_initial_call=True,
)
def parse_df(n_clicks, features_df):
    df = pd.read_json(features_df, orient='index')

    return dcc.send_data_frame(df.to_csv, "features.csv")


# Extract features from CTG trace and save to Store
@app.callback(Output('feature-data', 'data'),
              Input('csv-data', 'data'),
              Input('feature-selection', 'value'),
              prevent_initial_call=True)
def feature_extraction(json_csv, data):

    df = pd.read_json(json_csv, orient='split')

    features = pd.DataFrame()

    def baseline(df):
        value_add = 0
        baseline_data = []
        TEN_MIN = 2400
        # Gets the Baseline over 10 minute windows
        for i in range(len(df)):
            value = df.loc[i, 'fhr']
            if value != 0:
                value_add += value

            if i % TEN_MIN == 0 and i != 0:
                baseline_data.append((value_add / TEN_MIN))
                value_add = 0

        baseline_data.append((value_add / (i % TEN_MIN)))

        return baseline_data

    def variability(df):
        ONE_MIN = 240
        bandwidth = []
        variability_data = []
        bw = 0
        # Gets the Variability over 1 minute windows (Normal 5-25bpm)
        for i in range(len(df)):
            value = df.loc[i, 'fhr']
            if value != 0:
                bandwidth.append(value)

            if i % ONE_MIN == 0 and i != 0:
                max_bw = max(bandwidth)
                min_bw = min(bandwidth)
                bw = max_bw - min_bw
                variability_data.append(bw)
                bandwidth = []

            if i == len(df):
                max_bw = max(bandwidth)
                min_bw = min(bandwidth)
                bw = max_bw - min_bw
                variability_data.append(bw)
                bandwidth = []

        return variability_data

    def deceleration(df):
        deceleration_data = []
        TEN_MINUTES = 2400

        baseline_data = baseline(df)
        epoch = 0
        for i in range(len(df)):
            value = df.loc[i, 'fhr']
            if i % TEN_MINUTES == 0 and i != 0:
                epoch += 1
            deviation = baseline_data[epoch] - value
            deceleration_data.append(deviation)
        for j in range(len(deceleration_data)):
            if deceleration_data[j] >= 0:
                deceleration_data[j] = 0
        return deceleration_data

    def acceleration(df):
        acceleration_data = []
        TEN_MINUTES = 2400

        baseline_data = baseline(df)
        epoch = 0
        for i in range(len(df)):
            value = df.loc[i, 'fhr']
            if i % TEN_MINUTES == 0 and i != 0:
                epoch += 1
            deviation = baseline_data[epoch] - value
            acceleration_data.append(deviation)
        for j in range(len(acceleration_data)):
            if acceleration_data[j] <= 0:
                acceleration_data[j] = 0
        return acceleration_data

    baseline_df = pd.DataFrame({"Baseline": baseline(df)})
    variability_df = pd.DataFrame({"Variability": variability(df)})
    deceleration_df = pd.DataFrame({"Decelerations": deceleration(df)})
    acceleration_df = pd.DataFrame({"Accelerations": acceleration(df)})

    def automated_figo(df, baseline_df, variability_df, deceleration_df):
        auto_figo = pd.DataFrame()
        baseline_annotations = []
        variability_annotations = []
        deceleration_annotations = []

        #Baseline
        for i in range(len(baseline_df)):
            if i + 2 <= len(baseline_df):
                compare_list = []

                for i in range(3):
                    compare_list.append(baseline_df[i])

                epoch_baseline_max = max(compare_list)
                epoch_baseline_min = min(compare_list)

                if epoch_baseline_min < 110 or epoch_baseline_max > 160:
                    baseline_annotations.append(1)
                else:
                    baseline_annotations.append(0)

        #Deceleration
        for i in range(0, len(deceleration_df), 2400):
            decel_epoch = []
            deceleration = []

            annotation = 0
            for j in range(0, 7200):
                decel_epoch.append(deceleration_df[i + j])

                if deceleration_df[i + j] < -15:

                    deceleration.append(deceleration_df[i + j])
                    if len(deceleration) > 720:
                        annotation = 1

                    if (deceleration.index(min(deceleration)) -
                            len(deceleration)) > 120 or (deceleration.index(
                                min(deceleration))) > 120:
                        annotation = 1
                else:
                    decel_epoch = []

                deceleration_annotations.append(annotation)

        #Variability
        for i in range(0, len(variability_df), 10):
            if i + 29 <= len(variability_df):
                compare_list = []

                for j in range(30):
                    compare_list.append(variability_df[i + j])

                min_var = min(compare_list)
                max_var = max(compare_list)

                if min_var < 25 or max_var > 5:
                    variability_annotations.append(0)
                else:
                    variability_annotations.append(1)

        baseline_ann = pd.DataFrame({"Baseline": baseline_annotations})
        variability_ann = pd.DataFrame(
            {"Variability": variability_annotations})
        deceleration_ann = pd.DataFrame(
            {"Decelerations": deceleration_annotations})

        auto_figo = pd.concat([auto_figo, baseline_ann], axis=1)
        auto_figo = pd.concat([auto_figo, variability_ann], axis=1)
        auto_figo = pd.concat([auto_figo, deceleration_ann], axis=1)
        return auto_figo

    features = pd.concat([features, baseline_df], axis=1)
    features = pd.concat([features, variability_df], axis=1)
    features = pd.concat([features, deceleration_df], axis=1)
    features = pd.concat([features, acceleration_df], axis=1)

    return features.to_json(orient='index')


# Feature Graphs
@app.callback(Output('Feature-graph', 'children'),
              Input('feature-data', 'data'),
              Input('feature-selection', 'value'),
              Input('epoch-select', 'value'),
              Input('slider-h', 'value'),
              Input('slider-w', 'value'),
              prevent_initial_call=True)
def feature_graph(json_csv, feature_select, epoch, height, width):

    df = pd.read_json(json_csv, orient='index')

    config = dict({
        'scrollZoom': False,
        'displaylogo': False,
        'displayModeBar': True
    })

    fig = make_subplots(rows=4,
                        cols=1,
                        shared_xaxes=False,
                        shared_yaxes=False,
                        vertical_spacing=0.1)

    if "Baseline" in feature_select:  # 3 per epoch
        fig.add_trace(row=1,
                      col=1,
                      trace=go.Scatter(x=df.index,
                                       y=df['Baseline'],
                                       mode='lines',
                                       name='Baseline'))
        fig.add_trace(row=1,
                      col=1,
                      trace=go.Scatter(x=[0, 12],
                                       y=[110, 110],
                                       mode='lines',
                                       name='Baseline Lower Limit'))
        fig.add_trace(row=1,
                      col=1,
                      trace=go.Scatter(x=[0, 12],
                                       y=[160, 160],
                                       mode='lines',
                                       name='Baseline Upper Limit'))
        fig.update_xaxes(title_text="Baseline", row=1, col=1, range=[0, 12])
        fig.update_yaxes(title_text="BPM", row=1, col=1)

    if "Variability" in feature_select:  # 30 per epoch
        fig.add_trace(row=2,
                      col=1,
                      trace=go.Scatter(x=df.index,
                                       y=df['Variability'],
                                       mode='lines',
                                       name='Variability'))
        fig.add_trace(row=2,
                      col=1,
                      trace=go.Scatter(x=[0, 120],
                                       y=[5, 5],
                                       mode='lines',
                                       name='Variability Lower Limit'))
        fig.add_trace(row=2,
                      col=1,
                      trace=go.Scatter(x=[0, 120],
                                       y=[25, 25],
                                       mode='lines',
                                       name='Variability Upper Limit'))
        fig.update_xaxes(title_text="Variability",
                         row=2,
                         col=1,
                         range=[0, 120])
        fig.update_yaxes(title_text="BPM", row=2, col=1)

    if "Decelerations" in feature_select:
        fig.add_trace(row=3,
                      col=1,
                      trace=go.Scatter(x=df.index,
                                       y=df['Decelerations'],
                                       mode='lines',
                                       name='Decelerations'))
        fig.add_trace(row=3,
                      col=1,
                      trace=go.Scatter(
                          x=[0, 28800],
                          y=[-15, -15],
                          mode='lines',
                          name='Deceleration Amplitude Threshold'))

        fig.update_xaxes(title_text="Decelerations",
                         row=3,
                         col=1,
                         range=[0, 28800])
        fig.update_yaxes(title_text="BPM", row=3, col=1)

    if "Accelerations" in feature_select:
        fig.add_trace(row=4,
                      col=1,
                      trace=go.Scatter(x=df.index,
                                       y=df['Accelerations'],
                                       mode='lines',
                                       name='Accelerations'))
        fig.add_trace(row=4,
                      col=1,
                      trace=go.Scatter(
                          x=[0, 28800],
                          y=[15, 15],
                          mode='lines',
                          name='Acceleration Amplitude Threshold'))

        fig.update_xaxes(title_text="Accelerations",
                         row=4,
                         col=1,
                         range=[0, 28800])
        fig.update_yaxes(title_text="BPM", row=4, col=1)

    fig.update_layout(xaxis_range=[(epoch), (epoch + 12)],
                      title="Features",
                      yaxis_title="BPM",
                      height=int(height * 2),
                      width=int(width))
    return dcc.Graph(figure=fig, config=config)


# CTG Graph
@app.callback(Output('CTG-graph', 'children'),
              Input('csv-data', 'data'),
              Input('epoch-select', 'value'),
              Input('slider-h', 'value'),
              Input('slider-w', 'value'),
              prevent_initial_call=True)
def ctg_graph(json_csv, epoch, height, width):
    df = pd.read_json(json_csv, orient='split')
    time_shift = df.iat[1, 3]
    config = dict({
        'scrollZoom': False,
        'displaylogo': False,
        'displayModeBar': True
    })

    fig = make_subplots(rows=2,
                        cols=1,
                        shared_xaxes=True,
                        shared_yaxes=True,
                        vertical_spacing=0.02)

    fig.add_trace(row=1,
                  col=1,
                  trace=go.Scatter(x=df['time'],
                                   y=df['fhr'],
                                   mode='lines',
                                   name='FHR'))
    fig.add_trace(row=1,
                  col=1,
                  trace=go.Scatter(x=df['time'],
                                   y=df['mhr'],
                                   mode='lines',
                                   name='MHR'))
    fig.add_trace(row=2,
                  col=1,
                  trace=go.Scatter(x=df['time'],
                                   y=df['uc'],
                                   mode='lines',
                                   name='UC'))

    fig.update_layout(
        title="CTG",
        xaxis_title="Time",
        yaxis_title="BPM",
        height=int(height),
        width=int(width),
        xaxis_range=[(epoch * 10) + time_shift,
                     ((epoch * 10) + 30) + time_shift]  #30minute w/20 overlap
    )
    fig.update_yaxes(autorange=True, showgrid=True, row=2, col=1)
    fig.update_yaxes(range=[75, 200],
                     autorange=False,
                     showgrid=True,
                     row=1,
                     col=1)
    return dcc.Graph(figure=fig, config=config)


if __name__ == '__main__':
    app.run_server(debug=True, host='0.0.0.0', dev_tools_ui=False)