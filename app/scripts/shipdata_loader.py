import concurrent.futures
import threading
import logging
import os
import re
import json

import gspread
import pandas as pd
import numpy as np
import dask.dataframe as dd

from .baseloader import Loader
from ..core.config import settings

logger = logging.getLogger(__name__)
logging.root.setLevel(level=logging.INFO)

# ============= UTILITY FUNCTIONS =======================


def convert_dt(time_str):
    try:
        dt = pd.to_datetime(time_str)
    except Exception:
        logger.warning(f"Invalid time str: {time_str}")
        dt = np.NaN
    return dt


def clean_ship_verification(svdf):
    cleaned = svdf.dropna(how='all')
    cols = cleaned.columns

    names = []
    display_name = []
    units = []
    for col in cols:
        match = re.search(r"(((\w+-?\w?)\s?)+)(\[.*\])?", col)
        if match:
            matches = match.groups()
            name = matches[0].strip()
            unit = matches[-1]
            if unit:
                unit = unit.strip('[]')
            name = check_name(name)
            names.append(name.lower().replace(' ', '_'))
            display_name.append(name)
            units.append(unit)

    # for later, maybe save into separate table?
    discrete_samples_labels = {
        'name': names,
        'display_name': display_name,
        'unit': units,
    }

    cleaned.columns = names
    all_cleaned = cleaned.replace(-9999999.0, np.NaN).dropna(subset=['cruise'])
    time_cols = all_cleaned.columns[all_cleaned.columns.str.contains('time')]
    for col in time_cols:
        all_cleaned = all_cleaned.replace('-9999999', np.NaN).dropna(
            subset=[col]
        )
        all_cleaned.loc[:, col] = all_cleaned[col].apply(convert_dt)

    all_cleaned = all_cleaned.dropna(subset=time_cols)
    return all_cleaned.reset_index(drop='index'), discrete_samples_labels


def check_name(name):
    low_name = name.lower()
    if 'fluorescense' in low_name or 'flourescence' in low_name:
        logger.warning(
            f'Fluorescence is misspelled in {name}... replacing to Fluorescence'
        )
        new_name = name.replace('fluorescense'.title(), 'fluorescence'.title())
        new_name = new_name.replace(
            'flourescence'.title(), 'fluorescence'.title()
        )
    elif 'start positioning' in low_name:
        logger.warning(
            f'start positioning found in {name}... replacing to Start Position'
        )
        new_name = 'Bottom Depth at Start Position'
    elif 'phanalysis' in low_name:
        logger.warning(
            f'pH Analysis is strung together in {name}... fixing...'
        )
        new_name = name.replace('pHAnalysis', 'pH Analysis')
    elif 'ctd transmissometer flag' == low_name:
        logger.warning(f'Beam missing in {name}...')
        new_name = 'CTD Beam Transmissometer Flag'
    else:
        new_name = name
    return new_name


# ================================================================================


class LoadShipData(Loader):
    def __init__(self):
        Loader.__init__(self)
        self._name = "ShipDataLoader"
        self._ship_data_source = settings.SHIP_DATA_SOURCE
        self._ship_data_label_map = settings.SHIP_DATA_LABEL_MAP
        self._gspread_dir = os.path.join(
            os.path.expanduser("~"), '.config', 'gspread'
        )
        self._sources_df = None

        if not os.path.exists(self._gspread_dir):
            os.mkdir(self._gspread_dir)

        self.fetch_creds()
        self.start()

    def run(self):
        while self._in_progress:
            self._logger.info("Fetching Discrete Summary Sources...")
            gc = gspread.service_account()
            ws = gc.open('CAVA_ShipData').worksheet('Discrete Summary')
            ws_dict = ws.get_all_records()
            self._sources_df = pd.DataFrame(ws_dict)

            # Write source
            with self._fs.open(
                f'{self._cadai_bucket}/{self._ship_data_source}', mode='w'
            ) as f:
                f.write(json.dumps(ws_dict))

            self._fetch_profile_and_discrete()
            self._logger.info("Done loading ship data.")
            self._in_progress = False

    def _create_label_map(self, label_arrays):
        self._logger.info("Create label map...")
        missing_labels = label_arrays['CE'][
            ~label_arrays['CE'].index.isin(label_arrays['RS'].index)
        ]
        final_label_df = pd.concat([label_arrays['RS'], missing_labels])

        # Write source
        with self._fs.open(
            f'{self._cadai_bucket}/{self._ship_data_label_map}', mode='w'
        ) as f:
            f.write(final_label_df.to_json(orient='index'))

    def _fetch_profile_and_discrete(self):
        self._logger.info("Fetching Profiles and Discrete...")
        svdf_arrays = {}
        label_arrays = {}

        for idx, row in self._sources_df.iterrows():
            self._logger.info("------------------------")
            self._logger.info(row['cruise_id'])
            url = row['summary_url']
            self._logger.info(url)
            if url.endswith('.csv'):
                svdf = pd.read_csv(url, na_values=['-9999999'])
            elif url.endswith('.xlsx'):
                svdf = pd.read_excel(url, na_values=['-9999999'])

            if row['array_rd'] not in svdf_arrays:
                svdf_arrays[row['array_rd']] = []

            clean_svdf, discrete_sample_labels = clean_ship_verification(svdf)
            label_arrays[row['array_rd']] = pd.DataFrame(
                discrete_sample_labels
            ).set_index('name')
            if row['array_rd'] == 'CE':
                # Fix some O, 0 weirdness...
                if 'CEO2' in clean_svdf['station'].unique():
                    self._logger.warning('CEO2 found! Fixing to CE02...')
                clean_svdf.loc[:, 'station'] = clean_svdf['station'].apply(
                    lambda r: r.replace('O', '0')
                )
            clean_svdf.loc[:, 'cruise_id'] = row['cruise_id']
            final_svdf = clean_svdf.reset_index(drop=True)
            cleaned_final_svdf = self.check_types_and_replace(final_svdf)
            svdf_arrays[row['array_rd']].append(cleaned_final_svdf)

        svdf_dict = {
            k: pd.concat(v, sort=False) for k, v in svdf_arrays.items()
        }

        # Creates label mapping for Display Names and Units
        self._create_label_map(label_arrays)

        profile_list, discrete_list = [], []
        for k, v in svdf_dict.items():
            sampledf = v.copy()
            profile_df, discrete_df = self.parse_profile_and_discrete(
                sampledf, k
            )
            profile_list.append(profile_df)
            if any(
                discrete_df.columns.isin(['calculated_dic', 'calculated_pco2'])
            ):
                if all(discrete_df['calculated_dic'].isna()):
                    discrete_df.drop('calculated_dic', axis=1, inplace=True)
                if all(discrete_df['calculated_pco2'].isna()):
                    discrete_df.drop('calculated_pco2', axis=1, inplace=True)
            discrete_list.append(discrete_df)

        all_profiles = pd.concat(profile_list, sort=False).reset_index(
            drop=True
        )
        all_discrete = pd.concat(discrete_list, sort=False).reset_index(
            drop=True
        )
        apdd = dd.from_pandas(all_profiles, npartitions=2)
        addd = dd.from_pandas(all_discrete, npartitions=2)

        apdd.to_parquet(
            f"s3://{self._cadai_bucket}/{settings.SHIP_DATA_PROFILES}",
            write_index=False,
        )

        addd.to_parquet(
            f"s3://{self._cadai_bucket}/{settings.SHIP_DATA_DISCRETE}",
            write_index=False,
        )

    def fetch_creds(self):
        self._fs.get(
            os.environ['GOOGLE_SERVICE_JSON'],
            os.path.join(self._gspread_dir, 'service_account.json'),
        )

    def parse_profile_and_discrete(self, sampledf, array_rd):
        sampledf.loc[:, 'ctd_temperature'] = sampledf.apply(
            lambda row: self.check_double_sensors(row, 'ctd_temperature'),
            axis=1,
        )
        sampledf.loc[:, 'ctd_conductivity'] = sampledf.apply(
            lambda row: self.check_double_sensors(row, 'ctd_conductivity'),
            axis=1,
        )
        sampledf.loc[:, 'ctd_salinity'] = sampledf.apply(
            lambda row: self.check_double_sensors(row, 'ctd_salinity'), axis=1
        )
        sampledf.loc[:, 'date'] = sampledf['start_time'].apply(
            lambda row: row.strftime("%Y-%m")
        )
        sampledf.loc[:, 'area_rd'] = sampledf['station'].apply(self.set_area)

        profile_cols = sampledf.columns[
            sampledf.columns.str.contains('ctd|date|area_rd|cruise_id')
            & ~sampledf.columns.str.contains('flag')
            & ~sampledf.columns.str.contains(
                'file|bottle_closure_time|depth|latitude|longitude|beam_attenuation|oxygen_saturation|_2|_1'
            )
        ]
        discrete_cols = sampledf.columns[
            sampledf.columns.str.contains(
                'area_rd|cruise_id|date|ctd_pressure|discrete|calculated'
            )
            & ~sampledf.columns.str.contains('flag')
        ]

        profile_df = sampledf[profile_cols]
        profile_df.loc[:, 'array_rd'] = array_rd
        discrete_df = sampledf[discrete_cols]
        discrete_df.loc[:, 'array_rd'] = array_rd

        return profile_df, discrete_df

    def check_types_and_replace(self, df):
        value_str = ["ctd", "discrete", "calculated"]
        for k, v in df.dtypes.items():
            if (
                any(x in k for x in value_str)
                and 'file' not in k
                and 'bottle_closure_time' not in k
            ):
                if v == 'O':
                    do = df[k]
                    string_filter = do.str.contains('\w').fillna(False)
                    invalid_values = ','.join(do[string_filter].unique())
                    self._logger.warning(
                        f"** {k} ** contains invalid float values: {invalid_values}"
                    )
                    self._logger.warning(
                        "\tReplacing invalid values with NaNs..."
                    )
                    # Replace invalid values with NaNs
                    df.loc[string_filter, k] = np.NaN
                    # Set final dtype to float64
                    df.loc[:, k] = df[k].astype(np.float64)
        return df

    def check_double_sensors(self, row, var):
        if pd.isna(row[f'{var}_1']):
            if not pd.isna(row[f'{var}_2']):
                return row[f'{var}_2']
        return row[f'{var}_1']

    def set_area(self, station):
        st = station.lower()
        if re.search(r'(oregon\s+)?slope\s+base', st):
            return 'oregon-slope-base'
        elif re.search(r'axial\s+base', st):
            return 'axial-base'
        elif re.search(r'axial\s+caldera', st):
            return 'axial-caldera'
        elif re.search(r'(southern\s+)?hydrate\s+ridge', st):
            return 'southern-hydrate-ridge'
        elif re.search(r'mid\s+plate', st):
            return 'mid-plate'
        elif re.search(r'oregon\s+inshore|ce01', st):
            return 'oregon-inshore'
        elif re.search(r'oregon\s+shelf|ce02', st):
            return 'oregon-shelf'
        elif re.search(r'oregon\s+offshore|ce04', st):
            return 'oregon-offshore'
        elif re.search(r'washington\s+inshore|ce06', st):
            return 'washington-inshore'
        elif re.search(r'washington\s+shelf|ce07', st):
            return 'washington-shelf'
        elif re.search(r'washington\s+offshore|ce09', st):
            return 'washington-offshore'
        else:
            raise ValueError(f'Unknown area: {st}')
