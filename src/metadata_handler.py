#!/usr/bin/python
"""
Module class that handle file operations for the script.

Args (stdin): ctrl+c will soft stop the process similar to kill command or systemd stop <service>. kill -9 will hard stop.

Returns (stdout): As self.log.messages, if target_screen in self.log.is set to True.

Raises:
    Exception: If any error occurs, the exception is raised with a message describing the error.
"""

import config_handler as cm
import file_handler as fm

import logging
import os
import pandas as pd
import numpy as np
import uuid
import base58
import json
from typing import Any
import copy


# ---------------------------------------------------------------
# Constants used only in this module and not affected by the config file
POST_ORDER_COLUMN_PREFIX = "post_order-"
INDEX_COLUMN_PREFIX = "index-"
DATA_FILE_COLUMN_PREFIX = "file-"
AGGREGATION_SEPARATOR = ", "


# --------------------------------------------------------------
class DataHandler:
    def __init__(self, config: cm.Config, log: logging.Logger) -> None:
        """Initialize the FileHandler object with the configuration and self.log.er objects.

        Args:
            config (cm.Config): Configuration object.
            log.(lm.Logger): self.log.er object.
        """
        self.config: cm.Config = config
        """Configuration object."""
        self.log: logging.Logger = log
        """Application log object."""
        self.file: fm.FileHandler = fm.FileHandler(config=config, log=log)
        """FileHandler object."""

        self.pending_metadata_processing: bool = True
        """Flag to indicate that there is metadata needs to be processed."""
        self.data_files_to_ignore: dict[str, set[str]] = {
            k: set() for k in self.config.data_file_regex.keys()
        }
        """List of data files that were processed but not found in the reference data. To be processed only if the reference data is updated."""

        self.unique_id: str = base58.b58encode(uuid.uuid4().bytes).decode("utf-8")
        """Unique identifier for the in class column naming."""
        self.index_column: str = f"{INDEX_COLUMN_PREFIX}{self.unique_id}"
        """Index column name. Used to concatenate the values of the columns defined as keys."""
        self.data_file_column: str = f"{DATA_FILE_COLUMN_PREFIX}{self.unique_id}"
        """Data file control column name. Used to concatenate the filenames of the data files when multiple columns are defined."""
        self.post_order_column: str = f"{POST_ORDER_COLUMN_PREFIX}{self.unique_id}"
        """Post order column name. Used to keep ordering of the rows in the DataFrame."""
        self._replace_empty_sorting_value()
        self.ordering_index: dict[str, int] = {}
        """Index used for sequentially ordering rows in the various tables if no ordering column is defined. """

        self.pk_unmerge_map: dict[str, dict[str, list[str]]] = {}
        """ Dictionary mapping old and new primary keys to be used when for fixing merged PK rows. """

        df, col = self.read_reference_df()

        self.ref_df: dict[str, pd.DataFrame] = df
        """Dictionary with various dataframes containing the reference metadata in various tables."""
        self.ref_cols: dict[str, list[str]] = col
        """Dictionary with list of columns in in each reference DataFrame."""

        # If all tables were loaded, save the reference file from the dataframe loaded, considering corrections that may have been performed.
        persist_ref_df = True
        for df in self.ref_df.values():
            if df.empty:
                persist_ref_df = False

        if persist_ref_df:
            if not self.persist_reference():
                raise (
                    RuntimeError(
                        "Error saving the reference data after loading. Check configuration and file permissions."
                    )
                )

        self.next_pk_counter: dict[str, int] = self._initialize_next_pk_counter()
        """ Dictionary with initial number to be used as primary keys in each table. The key is the table name and the value is the number of free primary keys. """
        self.pk_mod_table: dict[str, dict[str, str]] = {}
        """ Dictionary with the table name and key associated with the primary key in relative (in file) indexing and absolute (in reference data) indexing. """

    # --------------------------------------------------------------
    def _replace_empty_sorting_value(self) -> None:
        """Process the row sorting dictionary to ensure all values are lists.

        Args:
            sort_by (Dict[str, str]): The original dictionary with sorting values.

        Returns:
            Dict[str, str]: The processed dictionary with lists as values.
        """

        # Use dictionary comprehension to identify keys needing default values
        empty_keys = {k for k, v in self.config.rows_sort_by.items() if not v}

        # Bulk update only the keys that need changing
        default_value = {
            cm.SORT_BY_KEY: [self.post_order_column],
            cm.ASCENDING_SORT_KEY: True,
        }

        if empty_keys:
            self.config.rows_sort_by.update({k: default_value for k in empty_keys})

    # --------------------------------------------------------------
    def _initialize_next_pk_counter(self) -> dict[str, int]:
        """Initialize the free primary key counter for each table in the reference data.

        Returns:
            dict[str, int]: Dictionary with the initial number to be used as primary keys in each table.
        """

        next_pk_counter = {}
        for table in self.ref_df.keys():
            # get the maximum value of the primary key column in the reference DataFrame
            try:
                pk_column = self.config.table_associations[table][cm.PK_KEY][
                    cm.NAME_KEY
                ]
            except KeyError:
                self.log.debug(
                    f"Table {table} does not have a primary key column defined in the config file."
                )
                continue

            try:
                if not pd.api.types.is_integer_dtype(self.ref_df[table][pk_column]):
                    self.ref_df[table][pk_column] = self.ref_df[table][
                        pk_column
                    ].astype(int)

                max_pk = self.ref_df[table][pk_column].max()
            except Exception as e:
                self.log.debug(
                    f"Using 1 as starting primary key value for table {table}: {e}"
                )
                max_pk = np.int64(0)

            next_pk_counter[table] = max_pk + 1

        return next_pk_counter

    # --------------------------------------------------------------
    def drop_na(self, df: pd.DataFrame, table: str, file: str) -> pd.DataFrame:
        """Drop rows from the DataFrame where the ID column has a null value in any variant form, including NA, NaN, strings such as '<NA>', 'NA', 'N/A', 'None', 'null' and empty strings.

        Args:
            df (pd.DataFrame): DataFrame to process.
            table (str): Name of the table to be used in the log message.
            file (str): File name to be used in the log message.

        Returns:
            pd.DataFrame: DataFrame with the rows where the ID column is not null.
        """

        rows_before = df.shape[0]

        df = df[~df[self.index_column].isin(self.config.null_string_values)]

        df = df.dropna(subset=[self.index_column])

        removed_rows = rows_before - df.shape[0]
        if removed_rows:
            self.log.info(
                f"Removed {removed_rows} rows with null values in key column(s) in table {table}, file '{file}'"
            )

        return df

    # --------------------------------------------------------------
    def _custom_agg(self, series: pd.Series) -> str:
        """Custom aggregation function to be used in the groupby method. Null is kept as Null, single value is kept as is, and multiple values are concatenated with a comma separator.

        Args:
            series (pd.Series): Series to be aggregated.

        Returns:
            str: Aggregated value.
        """

        non_null_values = series.dropna().unique()

        match len(non_null_values):
            case 0:
                return None
            case 1:
                return non_null_values[0]
            case _:
                return AGGREGATION_SEPARATOR.join(non_null_values)

    # --------------------------------------------------------------
    """Fix aggregated primary key values to ensure uniqueness and consistency after merging duplicate rows.
    
    Args:
        df (pd.DataFrame): DataFrame with aggregated rows.
        table (str): Name of the table that contains rows with aggregated pk.
        file (str): File name to be used in the log message.
    Returns:
        pd.DataFrame: DataFrame with fixed primary key values.
    """

    def _map_aggregated_pk(
        self, df: pd.DataFrame, table: str, file: str
    ) -> pd.DataFrame:
        # Test if self.config.table_associations has the table defined
        if table not in self.config.table_associations:
            self.log.debug(
                f"Table {table} does not have a table association defined in the config file. No primary key fix will be applied."
            )
            return df

        # get the primary key column name
        pk_info = self.config.table_associations.get(table, {}).get(cm.PK_KEY, None)
        pk_column = pk_info.get(cm.NAME_KEY, None) if pk_info else None

        # get rows in which the string defined in AGGREGATION_SEPARATOR appears in the primary key column
        if pk_column and pk_column in df.columns:
            aggregated_pk_rows = df[
                df[pk_column].astype(str).str.contains(AGGREGATION_SEPARATOR, na=False)
            ]

            if not aggregated_pk_rows.empty:
                self.log.debug(
                    f"Detected {len(aggregated_pk_rows)} aggregated primary key values in table {table}, file {file}"
                )

                for idx in aggregated_pk_rows.index:
                    # split the PK value by the AGGREGATION_SEPARATOR string
                    pk_values = str(aggregated_pk_rows.at[idx, pk_column]).split(
                        AGGREGATION_SEPARATOR
                    )

                    # Create a map for later processing of the merged keys.
                    # Need to wait until all tables are loaded to perform the correction since the tables that use the pk may not be loaded yet
                    self.pk_unmerge_map.setdefault(table, {})[pk_values[0]] = pk_values[
                        1:
                    ]

                    # replace the value of the row by the pk_values[0]
                    df.at[idx, pk_column] = pk_values[0]

        return df

    # --------------------------------------------------------------
    def _create_index(self, df: pd.DataFrame, table: str, file: str) -> pd.DataFrame:
        """Create an index for the DataFrame based on the columns defined in the config file.
        The index is created by concatenating the values of the columns defined in the config file.
        If rows with duplicate index values are found, they are merged using a custom aggregation function.

        Args:
            df (pd.DataFrame): DataFrame to process.
            table (str): Name of the table to be processed.
            file (str): File name to be used in the log message.

        Returns:
            pd.DataFrame: DataFrame with the index column created.
        """

        if self.config.key_columns is None:
            self.log.debug(
                "No key columns defined in config. No index will be created."
            )
            return df

        if table not in self.config.key_columns:
            self.log.debug(
                f"No key columns defined for table {table} to use for processing file {file}"
            )
            return df

        columns = list(self.config.key_columns[table])

        try:
            # create a column to be used as index, merging the columns in index_column list
            df = df.assign(
                **{self.index_column: df[columns].astype(str).agg("-".join, axis=1)}
            )

            # drop rows in which the column with name defined in the self.index_column has value null
            df = self.drop_na(df=df, table=table, file=file)

            # Identify rows with duplicate unique_name values
            duplicate_ids = df[self.index_column].duplicated(keep=False)
            duplicate_rows = df[duplicate_ids]

            if not duplicate_rows.empty:
                self.log.warning(
                    f"Data key repeated in {len(duplicate_rows)} rows in {file}, table {table}. Rows will be merged"
                )
                # Apply the custom aggregation function to the duplicate rows
                aggregated_rows = duplicate_rows.groupby(self.index_column).agg(
                    self._custom_agg
                )

                # fix aggregated PK
                aggregated_rows = self._map_aggregated_pk(aggregated_rows, table, file)

                # get the rows that are not duplicated
                unique_rows = df[~duplicate_ids]
                unique_rows = unique_rows.set_index(self.index_column)

                # Combine the unique rows with the aggregated rows
                df = pd.concat([unique_rows, aggregated_rows])
            else:
                df = df.set_index(self.index_column)

        except KeyError as e:
            self.log.error(
                f"Key error in dataframe from file {file}, table {table}: {e}"
            )
            return pd.DataFrame()
        except Exception as e:
            self.log.error(
                f"Error creating index in dataframe from file {file}, table {table}: {e}"
            )
            return pd.DataFrame()

        return df

    # --------------------------------------------------------------
    def _set_types(self, df: pd.DataFrame, table: str, file: str) -> pd.DataFrame:
        """Set the types of the columns in the DataFrame based on the config file.
        The types are set according to the config file for table association

        Args:
            df (pd.DataFrame): DataFrame to process.
            table (str): Name of the table to be used as defined in the config file.
            file (str): File name to be used in the log message.

        Returns:
            pd.DataFrame: DataFrame with the types set.
        """

        assoc = self.config.table_associations.get(table, None)
        if assoc:
            pk_info = assoc.get(cm.PK_KEY, None)
            if pk_info:
                pk_column = pk_info.get(cm.NAME_KEY, None)
                if (
                    pk_column
                    and pk_column in df.columns
                    and pk_info.get(cm.INT_TYPE_KEY, False)
                ):
                    df[pk_column] = df[pk_column].astype(int)
            fk_info = assoc.get(cm.FK_KEY, None)
            if fk_info:
                for fk_table, fk_column in fk_info.items():
                    if self.config.table_associations[fk_table][cm.PK_KEY].get(
                        cm.INT_TYPE_KEY, False
                    ):
                        df[fk_column] = df[fk_column].astype(int)
        else:
            self.log.debug(
                f"No table association defined for table {table}. No types will be set."
            )

        return df

    # --------------------------------------------------------------
    def _sort_dataframe(self, df: pd.DataFrame, table: str) -> pd.DataFrame:
        """Sort the DataFrame by the columns defined in the config file. The index is created by concatenating the values of the columns defined in the config file.

        Args:
            df (pd.DataFrame): DataFrame to process.
            table (str): Name of the table to be used as defined in the config file.

        Returns:
            pd.DataFrame: DataFrame with the index column created.
        """

        index_value = self.ordering_index.get(table, 0)
        df[self.post_order_column] = range(index_value, index_value + len(df))
        self.ordering_index[table] = index_value + len(df)

        return df

    # --------------------------------------------------------------
    def _create_data_file_control_column(
        self, df: pd.DataFrame, table: str
    ) -> pd.DataFrame:
        """Create a column with the filenames of the data files to which the metadata refers to.
        The column is created by concatenating the values of the columns defined in the config file.

        Args:
            df (pd.DataFrame): DataFrame to process.
            table (str): Name of the table to be used as defined in the config file.

        Returns:
            pd.DataFrame: DataFrame with the filenames column created.
        """

        if self.config.columns_data_filenames is None:
            self.log.debug("No data filenames control column defined in config.")
            return df

        if table not in self.config.columns_data_filenames:
            self.log.debug(
                f"No data filenames control column defined for table {table}. No data files to process."
            )
            return df

        columns_in_df = [
            col
            for col in self.config.columns_data_filenames[table]
            if col in df.columns
        ]

        if not columns_in_df:
            self.log.debug(
                f"No data filenames column in {table}. No data files to process."
            )
            return df

        # create a column to be used to search filenames in rows, merging the columns in list of filename columns
        data = {
            self.data_file_column: df[self.config.columns_data_filenames[table]]
            .astype(str)
            .agg("-".join, axis=1)
        }
        df = df.assign(**data)

        return df

    # --------------------------------------------------------------
    def _fix_create_data_published_column(
        self, df: pd.DataFrame, table: str
    ) -> pd.DataFrame:
        """Create or update the column assigned to indicate if the data files are present.
        If column already exists, replace null or empty row values with "False".
        Args:
            df (pd.DataFrame): DataFrame to process.
            table (str): Name of the table to be used as defined in the config file.
        Returns:
            pd.DataFrame: DataFrame with the data published column created.
        """

        if self.config.columns_data_published is None:
            self.log.debug("No data published control column defined in config.")
            return df

        if table not in self.config.columns_data_published:
            self.log.debug(
                f"No data published control column defined for table {table}. No data files to process."
            )
            return df

        for col in self.config.columns_data_published[table]:
            if col not in df.columns:
                df[col] = "False"
            else:
                df[col] = df[col].fillna("False")

        df[self.config.columns_data_published[table]] = df[
            self.config.columns_data_published[table]
        ].replace(self.config.null_string_values, "False")

        return df

    # --------------------------------------------------------------
    def _id_and_validate_table(
        self, df: pd.DataFrame, assigned_table: str, file: str
    ) -> tuple[bool, str]:
        """Identify and validate the table in the DataFrame according to required columns (columns in and keys) defined in the config file
        Args:
            df (pd.DataFrame): DataFrame to process.
            assigned_table (str): Name of the table to be used as defined in the config file.
            file (str): File name to be used in the log message.

        Returns:
            tuple[bool, str]: Tuple with a boolean indicating if the table is valid and the name of the table.

        """

        df_columns = set(df.columns.tolist())

        distance = {
            k: float("inf") for k in self.config.expected_columns_in_files.keys()
        }

        if assigned_table == self.config.default_multiple_object_key:
            assigned_table = None

        for table, required_columns in self.config.expected_columns_in_files.items():
            # compute the distance between the DataFrame columns and the required columns.
            # Required columns must be a subset of the DataFrame columns.
            # Smaller distance correspond to the dataframe that is the smaller superset of the required columns.
            # An empty column list will be a subset to all tables and the table with smallest number of columns will be returned.
            if required_columns.issubset(df_columns):
                distance[table] = len(df_columns - required_columns)

        # Find the table with minimum distance value
        min_distance_value = min(distance.values())

        # Find all tables with this minimum distance
        tables_with_min_distance = [
            table for table, dist in distance.items() if dist == min_distance_value
        ]

        # If there's only one table with minimum distance, use it
        if len(tables_with_min_distance) == 1:
            assigned_table = tables_with_min_distance[0]
        # If there are multiple tables with same minimum distance (tie)
        elif len(tables_with_min_distance) > 1:
            # If assigned_table is already set and is among the minimum distance tables, keep it
            if assigned_table and assigned_table in tables_with_min_distance:
                # Keep the current assigned_table value (no change needed)
                pass
            else:
                # Raise error if no predefined table is available for tie-breaking
                self.log.error(
                    f"Multiple tables ({tables_with_min_distance}) match the data equally well in file {file}"
                )
                raise ValueError(
                    f"Ambiguous table assignment in file {file}: {tables_with_min_distance}"
                )

        # Check if the assigned table has an infinite distance (no match)
        if distance[assigned_table] == float("inf"):
            self.log.warning(
                f"No valid table found in file {file}. Columns do not match any table."
            )
            return False, assigned_table

        return True, assigned_table

    # --------------------------------------------------------------
    def process_table(
        self, df: pd.DataFrame, table: str, file: str
    ) -> tuple[pd.DataFrame, list, str]:
        """Process the DataFrame to create, clean column names and other adjustments.
        Args:
            df (pd.DataFrame): DataFrame to process.
            table (str): Name of the table to be used as defined in the config file.
            file (str): File name to be used in the log message.

        Returns:
            pd.DataFrame: DataFrame with the data from the Excel file.
            list: List of columns in the DataFrame.
            str: Name of the table to be used as defined in the config file.
        """

        # Add columns that will be included in the output
        transformations = [
            lambda df: self._add_filename_column(df, table, file),
            lambda df: self._add_filename_data(df, table, file),
            lambda df: self._fix_create_data_published_column(df, table),
        ]

        [df := transform(df) for transform in transformations]

        # If the DataFrame still empty, log a message and return an empty DataFrame
        if len(df.columns) == 0:
            self.log.debug(
                f"No data in DataFrame for table {table} in file '{file}'. Returning empty DataFrame."
            )
            return pd.DataFrame(), [], table

        # Remove escaped characters from column names
        df.columns = self.config.limit_character_scope(df.columns.tolist())

        # Validate the table based on the required columns and keys defined in the config file
        valid_table, table = self._id_and_validate_table(df, table, file)

        if not valid_table:
            self.log.warning(f"No valid table data found in file {file}.")
            return pd.DataFrame(), [], table

        # Get columns before final transformations that add control columns
        columns = df.columns.tolist()

        # Perform additional table transformation considering existing data and add control columns (not to be included in the output)
        transformations = [
            lambda df: self._create_data_file_control_column(df, table),
            lambda df: self._create_index(df, table, file),
            lambda df: self._set_types(df, table, file),
            lambda df: self._sort_dataframe(df, table),
        ]

        [df := transform(df) for transform in transformations]

        return df, columns, table

    # --------------------------------------------------------------
    def create_dataframe(self, data: dict) -> pd.DataFrame:
        """Create a DataFrame from list of dictionaries.
        The dictionary keys are the column names and the values are the column values.
        If the input is a list of dictionaries, each dictionary will be a row in the DataFrame.
        If the input is a single dictionary, the DataFrame will have a single row.

        Args:
            data (dict): Dictionary with the data to create the DataFrame.

        Returns:
            pd.DataFrame: DataFrame with the data from the dictionary.
        """

        if isinstance(data, list):
            return pd.DataFrame(data, dtype="string")
        elif isinstance(data, dict):
            return pd.DataFrame([data], dtype="string")
        elif data is None:
            self.log.debug("Input data is None. Returning an empty DataFrame.")
            return pd.DataFrame()
        else:
            self.log.error(
                f"Unsupported data type: {type(data)}. Expected list, dict, or None."
            )
            raise ValueError(f"Unsupported data type: {type(data)}")

    # --------------------------------------------------------------
    def _fix_merged_pk_values(
        self, new_data_df: dict[str, pd.DataFrame]
    ) -> dict[str, pd.DataFrame]:
        """Fix merged primary key values in the DataFrames after all tables have been loaded.
        Args:
            new_data_df (dict[str, pd.DataFrame]): Dictionary with the DataFrames containing various tables.
        Returns:
            dict[str, pd.DataFrame]: Dictionary with the DataFrames containing various tables with fixed primary key values.
        """

        # get affected table names and changed primary key values from the pk_unmerge_map, if any
        for table_with_merged_pk, merged_pk_values in self.pk_unmerge_map.items():
            # get names for tables that use the PK that were merged, as indicated in the pk_unmerge_map
            pk_info = self.config.table_associations.get(table_with_merged_pk, {}).get(
                cm.PK_KEY, None
            )
            fk_table_to_update = pk_info.get(cm.REFERENCED_BY_KEY, None)

            # change the FK values in the tables that use the merged PK to the new PK value, as defined in the pk_unmerge_map
            for table_using_fk in fk_table_to_update:
                for new_key, keys_to_replace in merged_pk_values.items():
                    fk_column = (
                        self.config.table_associations.get(table_using_fk, {})
                        .get(cm.FK_KEY, {})
                        .get(table_with_merged_pk, None)
                    )

                    # Get the data type of the target column
                    target_dtype = new_data_df[table_using_fk][fk_column].dtype

                    # Convert new_key to the target column's dtype before assignment
                    try:
                        typed_new_key = target_dtype.type(new_key)

                        # Convert each item in keys_to_replace, skipping any that fail
                        typed_keys_to_replace = [
                            target_dtype.type(k) for k in keys_to_replace
                        ]

                    except (ValueError, TypeError):
                        self.log.warning(
                            f"Could not convert keys dtype for column '{fk_column}' in table '{table_using_fk}'. Skipping."
                        )
                        continue

                    new_data_df[table_using_fk].loc[
                        new_data_df[table_using_fk][fk_column].isin(
                            typed_keys_to_replace
                        ),
                        fk_column,
                    ] = typed_new_key

        # clear the pk_unmerge_map for next file processing
        self.pk_unmerge_map = {}

        return new_data_df

    # --------------------------------------------------------------
    def read_metadata(
        self, file: str, suggested_table: str
    ) -> tuple[dict[str, pd.DataFrame], dict[str, list]]:
        """Read an metadata file and return a list of tuples with the DataFrame and the columns in the DataFrame.
        The file can be an Excel file, a CSV file or a JSON file.

        Args:
            file (str): Excel file to read.
            suggested_table (str): Name of the table associated with the file.

        Returns:
            dict[str,pd.DataFrame]: Dictionary with the DataFrames containing various tables.
            dict[str,list]: Dictionary with the lists of columns for each table.
        """

        new_data_df = {key: pd.DataFrame() for key in self.config.table_names}
        new_data_columns = {key: [] for key in self.config.table_names}
        add_remaining_data = False

        file_extension = os.path.splitext(file)[1]

        try:
            match file_extension:
                case ".xlsx":
                    # Read all worksheets from Excel file
                    with pd.ExcelFile(file) as excel_file:
                        sheet_names = excel_file.sheet_names

                        # create a copy of sheet_names to avoid modifying the original list with the for loop
                        sheets_pending_to_read = sheet_names.copy()

                        # If there are multiple worksheets
                        if len(sheet_names) > 1:
                            self.log.info(
                                f"XLSX file {file} contains multiple worksheets: {sheet_names}"
                            )

                            # Process each worksheet separately.
                            for sheet_name in sheet_names:
                                table = self.config.sheet_names.get(
                                    sheet_name, sheet_name
                                )

                                if table in new_data_df.keys():
                                    # Read the worksheet into a DataFrame
                                    new_df = excel_file.parse(
                                        sheet_name, dtype="string"
                                    )

                                    # Process the worksheet data
                                    new_df, columns, table = self.process_table(
                                        df=new_df, table=table, file=file
                                    )
                                    new_data_df[table] = new_df
                                    new_data_columns[table] = columns

                                    # remove the processed sheet name from the list of new_data_df
                                    sheets_pending_to_read.remove(sheet_name)

                        if sheets_pending_to_read:
                            if len(sheets_pending_to_read) == 1:
                                new_df = excel_file.parse(
                                    sheets_pending_to_read[0], dtype="string"
                                )
                                add_remaining_data = True
                            else:
                                self.log.warning(
                                    "Multiple worksheets in file {file}. Check configuration to include table names to all worksheets."
                                )

                case ".csv":
                    # Detect encoding first
                    encoding = self.file.test_file_encoding(file)

                    new_df = pd.read_csv(
                        file, dtype="string", encoding=encoding, sep=";"
                    )

                    add_remaining_data = True

                case ".json":
                    # Detect encoding first
                    encoding = self.file.test_file_encoding(file)

                    with open(file, "r", encoding=encoding) as json_file:
                        data = json.load(json_file)

                    # look for each defined table name in the json file and create a corresponding DataFrame
                    for table in new_data_df.keys():
                        if data and table in data:
                            new_df = self.create_dataframe(data[table])

                            new_df, columns, table = self.process_table(
                                df=new_df, table=table, file=file
                            )
                            new_data_df[table] = new_df
                            new_data_columns[table] = columns

                            del data[table]

                    # add the remaining data from the json file to the default base_key table
                    if data:
                        new_df = self.create_dataframe(data)
                        add_remaining_data = True

                case _:
                    self.log.error(f"Unsupported metadata file type: {file_extension}")

            if add_remaining_data:
                if suggested_table == self.config.default_multiple_object_key:
                    table = self.config.default_worksheet_key
                else:
                    table = suggested_table

                new_df, columns, table = self.process_table(
                    df=new_df, table=table, file=file
                )
                new_data_df[table] = new_df
                new_data_columns[table] = columns

            if not self.config.required_tables.issubset(set(new_data_df.keys())):
                self.log.warning(
                    f"File {file} does not contain all required tables: {self.config.required_tables}. No data will be processed from it."
                )
                return {}, {}

            # once finished loading all tables, fix merged PK values (if any)
            new_data_df = self._fix_merged_pk_values(new_data_df)

            return new_data_df, new_data_columns

        except Exception as e:
            self.log.error(f"Error reading metadata file {file}: {e}")
            return {}, {}

    # --------------------------------------------------------------
    def merge_lists(self, new_list: list, legacy_list: list) -> list:
        """Merge two lists into a single list
        Order of the elements in new_list keep minimum distance to the element order in the legacy_list.

        Args:
            new_list (list): List that will be the basis for the merged result.
            legacy_list (list): List that will be included.

        Returns:
            list: Merged list.
        """

        new_set = set(new_list)
        legacy_set = set(legacy_list)
        items_not_in_new = legacy_set - new_set

        merged_list = new_list

        if items_not_in_new:
            self.log.debug(
                f"Items present in the existing list that are not in the new list: {items_not_in_new}"
            )

            legacy_order = {item: i for i, item in enumerate(legacy_list)}
            new_order = {item: i for i, item in enumerate(new_list)}

            for item in items_not_in_new:
                keep_neighbor_search = True
                reached_beginning = False
                reached_end = False

                distance_to_neighbor = 1
                direction = 1  # 1 to previous, -1 to next
                position = legacy_order[item] - 1

                # If the first element in the legacy list is missing in the new list, the previous neighbor is None
                if position < 0:
                    direction = -1
                    position = legacy_order[item] + 1
                    reached_beginning = True

                while keep_neighbor_search:
                    try:
                        # if neighbor is found in the new list, insert the item in the new list at the same relative position, update the new_set and new_order and stop the search
                        if legacy_list[position] in new_set:
                            position = new_order[legacy_list[position]] + direction
                            merged_list.insert(position, item)
                            new_set.add(item)
                            new_order = {item: i for i, item in enumerate(new_list)}
                            keep_neighbor_search = False
                        else:
                            # if moving to the end of the list, increase distance to the neighbor and if not reached the beginning, try the other direction
                            if direction == -1:
                                distance_to_neighbor += 1
                                if not reached_beginning:
                                    direction = 1
                            # if moving to the beginning of the list, keep the distance and try the other direction except if reached the end, then keep the direction and increase distance
                            else:
                                if reached_end:
                                    distance_to_neighbor += 1
                                else:
                                    direction = -1

                            position = legacy_order[item] - (
                                distance_to_neighbor * direction
                            )
                    except IndexError:
                        # if hit one of the ends, change direction and try again, marking the end reached
                        if position < 0:
                            reached_beginning = True
                            direction = -1
                        else:
                            reached_end = True
                            distance_to_neighbor += 1
                            direction = 1

                        # if no neighbor is not found in the new list (maybe possible with empty initial list), insert the item at end and stop the search
                        if reached_beginning and reached_end:
                            merged_list.append(item)
                            keep_neighbor_search = False
                            reached_beginning = False
                            reached_end = False

                        # update the current search position considering the direction taken
                        position = legacy_order[item] - (
                            distance_to_neighbor * direction
                        )

        return merged_list

    # --------------------------------------------------------------
    def merge_dicts(
        self, new_dict: dict[str, list[str]], legacy_dict: dict[str, list[str]]
    ) -> dict[str, list[str]]:
        """Merge dictionaries with column lists from multiple tables.
        Column lists with the same key are combined into single list,
        The order of the elements in new_dict keeps minimum distance to the element order in the legacy_dict.

        Args:
            new_dict: Incoming dict with table lists.
            legacy_dict: Existing dict with table lists.

        Returns:
            Merged dictionary.
        """

        legacy_dict_copy = legacy_dict.copy()
        # merge keys that are both in the legacy and the new column list
        for key in new_dict.keys():
            if key in legacy_dict:
                new_dict[key] = self.merge_lists(
                    new_list=new_dict[key], legacy_list=legacy_dict[key]
                )
                legacy_dict_copy.pop(key, None)

        # add any remaining table column list, not present in the new dict, to the result dict.
        if legacy_dict_copy:
            new_dict.update(legacy_dict_copy)

        return new_dict

    # --------------------------------------------------------------
    def update_reference_data(
        self, new_data_df: dict[str, pd.DataFrame], file: str
    ) -> None:
        """Update the reference data with the new data from the metadata file.
        Args:
            new_data_df (dict[str,pd.DataFrame]): Dictionary with the DataFrames containing various tables.
            file (str): The metadata file being processed.
        """

        # update reference with tables without associations
        unassociated_tables = self.config.unassociated_tables.intersection(
            new_data_df.keys()
        )

        for table in unassociated_tables:
            if new_data_df.get(table, pd.DataFrame()).empty:
                continue

            update_df, add_df = self.split_df_rows_add_update(new_data_df, table)

            self._apply_updates_to_reference_data(update_df, add_df, table)

            self.log.info(
                f"Table {table} from file {file}: {len(update_df.get(table, pd.DataFrame()))} rows updated, {len(add_df.get(table, pd.DataFrame()))} rows added."
            )

        associated_tables = new_data_df.keys() - unassociated_tables
        if associated_tables:
            self.update_associated_tables(new_data_df, file)

    # --------------------------------------------------------------
    def update_associated_tables(
        self, new_data_df: dict[str, pd.DataFrame], file: str
    ) -> None:
        """This method loops through all dataframes in new_data_df dict, updating all primary and foreign keys.
        For all tables, a control of which keys were checked and which ones were not is kept.
        It starts looking for tables in which only the primary keys remains unchecked, and updates them first, updating the corresponding foreign keys in other tables keys
        The process is repeated until all keys are checked or no more keys can be updated.

        Args:
            new_data_df (dict[str,pd.DataFrame]): Dictionary with the DataFrames containing various tables.
            file (str): The metadata file being processed.

        Returns:
            None
        """

        # Create a deep copy to avoid mutating the original config
        associations_to_check = copy.deepcopy(self.config.table_associations)
        """ association structure to be popped to indicate that the PK or FK of a table was checked and updated."""
        success_running_step: bool = True
        """ True if any primary/foreign key was updated in the last iteration."""
        pk_map: dict[str, dict[str, str]] = {}
        """ table -> {old_pk -> new_pk} """

        while associations_to_check and success_running_step:
            success_running_step = False

            for table in list(associations_to_check.keys()):
                # get the dataframe for the table, if the dataframe is empty, remove the table from the associations_to_check dict and continue
                df = new_data_df.get(table, pd.DataFrame())
                if df.empty:
                    associations_to_check.pop(table)
                    success_running_step = True
                    continue

                # get the table association info from the config file, if not found, remove the table from the associations_to_check dict and continue
                assoc = associations_to_check.get(table, None)
                if not assoc:
                    associations_to_check.pop(table)
                    success_running_step = True
                    continue

                pk_info_to_check = assoc.get(cm.PK_KEY, None)
                fk_info_to_check = assoc.get(cm.FK_KEY, None)
                if pk_info_to_check is not None:
                    # process only tables with unchecked primary keys where all foreign keys are checked
                    if fk_info_to_check:
                        success_running_step = True
                        continue
                    else:
                        associations_to_check[table].pop(cm.FK_KEY, None)

                    # for the table with unchecked primary key, split the dataframe into rows to update and rows to add, mapping old and new primary keys
                    update_df, add_df = self.split_df_rows_add_update(
                        new_data_df, table
                    )

                    pk_map[table] = {}
                    # apply changes to the PK in the update_dfs dataframes
                    pk_map, update_df = self._update_primary_keys(
                        pk_map, update_df, table
                    )

                    # apply changes to the PK in the add_dfs dataframes
                    pk_map, add_df = self._assign_primary_keys(pk_map, add_df, table)

                    self._apply_updates_to_reference_data(update_df, add_df, table)

                    # apply changes to the FK in the update_dfs and add_dfs dataframes of other tables, popping the changed FK from the associations_to_check dict
                    new_data_df, associations_to_check = self._update_foreign_keys(
                        pk_map,
                        new_data_df,
                        associations_to_check,
                        table,
                        file,
                    )

                    # Once pk is checked table may be removed. Remember that all FK have been processed prior to the PK processing.
                    associations_to_check.pop(table, None)
                    success_running_step = True

        if not success_running_step:
            self.file.trash_it(file=file, overwrite=self.config.trash_data_overwrite)
            raise ValueError(
                f"Could not update all primary/foreign keys for metadata from file {file}. File will be moved to trash. Check configuration and metadata file before attempting to reprocess."
            )

        return

    # --------------------------------------------------------------
    def split_df_rows_add_update(
        self, new_data_df: dict[str, pd.DataFrame], table: str
    ) -> tuple[dict[dict[str, pd.DataFrame], dict[str, pd.DataFrame]]]:
        """Split new data into rows that need to be updated and rows that need to be added
        Create a primary key mapping to associate the PK in the file to the PK in the reference DF.

        Args:
            new_data_df: Dictionary with DataFrames containing various tables.
            table: Name of the table to be processed. new_data_df[table] must exist.

        Returns:
            tuple: (update_dfs, add_dfs)
                - update_df: DataFrame with rows to update in table
                - add_dfs: DataFrame with row to add in table
        """
        df = new_data_df.get(table, pd.DataFrame())

        # Find common indexes between new data and reference data
        common_indexes = df.index.intersection(self.ref_df[table].index)

        if common_indexes.empty:
            # Set rows to update empty and copy all rows to add
            update_df = pd.DataFrame(columns=df.columns)
            add_df = df.copy()
        else:
            # Set rows to update as the intersection and the remaining as rows to add
            update_df = df.loc[common_indexes].copy()
            add_df = df.drop(common_indexes).copy()

        return update_df, add_df

    # --------------------------------------------------------------
    def _update_primary_keys(
        self,
        pk_map: dict[str, dict[str, str]],
        update_df: pd.DataFrame,
        table: str,
    ) -> tuple[dict[dict[str, str]], pd.DataFrame]:
        """Update the PK in the update DataFrame to match the reference DF.
        Args:
            pk_map (dict[str, dict[str, str]]): Dictionary with primary key mappings for each table. Must contain the table being processed.
            update_df (pd.DataFrame): DataFrame containing rows to update.
            table (str): Name of the table to be processed. Table association with PK/FK must be defined in the config file.
        Returns:
            tuple: (pk_map, update_dfs)
                - pk_map: Updated dictionary mapping old PKs to new PKs by table
                - update_df: DataFrame with rows to update in table with updated PKs
        """

        # Check if there is data to update
        if update_df.empty:
            return pk_map, update_df

        pk_column = (
            self.config.table_associations.get(table, {})
            .get(cm.PK_KEY, {})
            .get(cm.NAME_KEY, None)
        )

        if not pk_column:
            return pk_map, update_df

        # Get old and new PKs
        old_pks = update_df[pk_column]
        new_pks = self.ref_df[table].loc[update_df.index, pk_column]

        # Build mapping only for distinct pairs of old_pks and new_pks
        pk_pairs = list(zip(old_pks, new_pks))
        distinct_pk_pairs = {old: new for old, new in pk_pairs}

        if distinct_pk_pairs:
            pk_map.setdefault(table, {}).update(distinct_pk_pairs)

        # Update the PKs in the update dataframe (in case they differ)
        update_df[pk_column] = new_pks.values

        return pk_map, update_df

    # --------------------------------------------------------------
    def _assign_primary_keys(
        self,
        pk_map: dict[str, dict[str, str]],
        add_df: pd.DataFrame,
        table: str,
    ) -> tuple[dict[dict[str, str]], pd.DataFrame]:
        """Update the PK in the update DataFrame to match the reference DF.
        Update the PK in the add DataFrame to match the next available PK in the reference DF.

        Args:
            pk_map (dict[str, dict[str, str]]): Dictionary with primary key mappings for each table. Must contain the table being processed.
            add_df (pd.DataFrame): DataFrame containing rows to add.
            table (str): Name of the table to be processed. Table association with PK/FK must be defined in the config file.

        Returns:
            tuple: (pk_map, add_dfs)
                - pk_map: Updated dictionary mapping old PKs to new PKs by table
                - add_df: DataFrame with rows to add in table with updated PKs
        """

        # Check if there is data to add
        if add_df.empty:
            return pk_map, add_df

        pk_info = self.config.table_associations.get(table, {}).get(cm.PK_KEY, {})
        pk_column = pk_info.get(cm.NAME_KEY, None)
        pk_int_type = pk_info.get(cm.INT_TYPE_KEY, False)

        if not pk_column or not pk_int_type:
            return pk_map, add_df

        # Initialize the primary_table entry in pk_mod_primary_table if it doesn't exist
        pk_map.setdefault(table, {})

        # If PK is defined as a sequential int number
        if pk_int_type:
            distinct_pks = add_df[pk_column].drop_duplicates().tolist()
            min_value = add_df[pk_column].min()
            max_value = add_df[pk_column].max()

            offset = self.next_pk_counter[table] - min_value

            # if the PK is relative and an int, add the next_pk_counter value to the minimum value
            add_df[pk_column] = add_df[pk_column] + offset

            # update the next_pk_counter value for the primary_table
            self.next_pk_counter[table] += max_value

            # update pk_map dict with values from distinct_pks with added offset
            new_pks = pd.Series(distinct_pks) + offset
            pk_map.setdefault(table, {}).update(
                dict(zip(distinct_pks, new_pks.tolist()))
            )

        # else, if PK is not a sequential int, generate a new UI
        else:
            # Extract original primary key values
            old_pks = add_df[pk_column].tolist()

            # Create a list of IDs sequentially counting from self.next_pk_counter[primary_table] until self.next_pk_counter[primary_table] + len(original_pks)
            new_pks = list(
                range(
                    self.next_pk_counter[table],
                    self.next_pk_counter[table] + len(old_pks),
                )
            )

            # Store mapping of original to new primary keys
            pk_map.setdefault(table, {}).update(dict(zip(old_pks, new_pks)))

            # Replace the primary key column values with the new keys
            add_df[pk_column] = add_df[pk_column].map(pk_map[table])

            # update self.next_pk_counter[primary_table]
            self.next_pk_counter[table] += len(old_pks)

        return pk_map, add_df

    # --------------------------------------------------------------
    def _update_foreign_keys(
        self,
        pk_map: dict[str, dict[str, str]],
        new_data_df: dict[str, pd.DataFrame],
        associations_to_check: dict[str, Any],
        table: str,
        file: str,
    ) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
        """Update foreign keys (FK) in existing dataframe based on key mappings,
        reindex dataframe considering new FK, and
        mark the corresponding changes in the associations_to_check dict.
        Args:
            pk_map (dict[str, dict[str, str]]): Dictionary with primary key mappings for
                each table. Must contain the table being processed.
            new_data_df (dict[str, pd.DataFrame]): Dictionary with DataFrames containing
                various tables.
            associations_to_check (dict[str, Any]): Dictionary with table associations
                to be checked for updates.
            table (str): Name of the table to be processed. Table association with PK/FK
                must be defined in the config file.
            file (str): The metadata file being processed.
        Returns:
            tuple: (new_data_df, associations_to_check)
                - new_data_df: Updated dictionary of DataFrames containing various tables
                - associations_to_check: Updated dictionary with table associations to be checked for updates
        """

        mappings = pk_map.get(table, None)

        referenced_by = (
            self.config.table_associations.get(table, {})
            .get(cm.PK_KEY, {})
            .get(cm.REFERENCED_BY_KEY, None)
        )

        if not referenced_by:
            return new_data_df, associations_to_check

        # Update foreign keys in all referencing tables using the pk_map
        for ref_table in referenced_by:
            fk_column = (
                self.config.table_associations.get(ref_table, {})
                .get(cm.FK_KEY, {})
                .get(table, None)
            )

            if (
                not fk_column
                or fk_column not in new_data_df.get(ref_table, pd.DataFrame()).columns
            ):
                continue

            new_data_df[ref_table][fk_column] = new_data_df[ref_table][
                fk_column
            ].replace(mappings)

            # Rebuild index for the table. Index includes the updated foreign key column.
            new_data_df[ref_table] = self._create_index(
                new_data_df[ref_table], ref_table, file
            )

            # Remove processed foreign keys from associations_to_check
            associations_to_check[ref_table][cm.FK_KEY].pop(table, None)

            # Remove FK_KEY if empty
            if not associations_to_check[ref_table][cm.FK_KEY]:
                associations_to_check[ref_table].pop(cm.FK_KEY, None)

        return new_data_df, associations_to_check

    # --------------------------------------------------------------
    def _apply_updates_to_reference_data(
        self,
        update_df: pd.DataFrame,
        add_df: pd.DataFrame,
        table: str,
    ) -> None:
        """Apply updates to reference data from both updated and new rows.

        Args:
            update_df: DataFrame with rows to update
            add_df: DataFrame with rows to add
            table: Table to be updated/extended in the reference data

        Returns:
            None
        """

        # apply updates using combine_first method
        if not update_df.empty:
            try:
                self.log.debug(f"Updating {update_df.shape[0]} rows in table {table}")

                self.ref_df[table] = self._add_missing_columns_from_df(
                    self.ref_df[table], update_df
                )

                self.ref_df[table] = update_df.combine_first(self.ref_df[table])

            except Exception as e:
                self.log.error(
                    self.config.exception_message_handling(
                        f"Error updating data in Table: {table}: Error: {e}"
                    )
                )

        # add new rows using concat method
        if not add_df.empty:
            try:
                self.log.debug(f"Adding {add_df.shape[0]} new rows to table {table}")

                self.ref_df[table] = self._add_missing_columns_from_df(
                    self.ref_df[table], add_df
                )

                self.ref_df[table] = pd.concat([self.ref_df[table], add_df])

            except Exception as e:
                self.log.error(
                    self.config.exception_message_handling(
                        f"Error adding data  in Table: {table}: Error: {e}"
                    )
                )

    # --------------------------------------------------------------
    def _add_missing_columns_from_df(
        self, target_df: pd.DataFrame, source_df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Add columns to target_df that are present in source_df but missing from target_df,
        preserving column names and data types from the source_df

        Args:
            target_df (pd.DataFrame): The DataFrame to add columns to.
            source_df (pd.DataFrame): The DataFrame to take columns and dtypes from.

        Returns:
            pd.DataFrame: The updated target_df with added columns.
        """
        new_columns = set(source_df.columns) - set(target_df.columns)
        if new_columns:
            dtype_dict = {col: source_df[col].dtype for col in new_columns}
            temp_df = pd.DataFrame(columns=list(new_columns)).astype(dtype_dict)
            target_df = pd.concat([target_df, temp_df], axis=1)

        return target_df

    # --------------------------------------------------------------
    def _add_filename_column(
        self, df: pd.DataFrame, table: str, file: str
    ) -> pd.DataFrame:
        """Complement the data in the reference DataFrame with metadata extracted from the filename and the file itself.

        Args:
            df : Dataframe into the new column with filename may be created.
            table (str): Name of the table to be used as defined in the config file.
            file (str): The metadata file being processed.

        Returns:
            pd.DataFrame: Updated DataFrame with the new data.
        """

        if self.config.add_filename is None:
            self.log.debug("No filename column required in the config file.")
            return df

        if table in self.config.add_filename.keys():
            if self.config.add_filename[table] in df.columns:
                self.log.debug(
                    f"Column `{self.config.add_filename[table]}` already exists in table `{table}` from file `{file}`. No filename column will be added."
                )
                return df

            new_column_name = self.config.add_filename[table]
            basename = os.path.basename(file)

            if df.empty:
                # Create a new DataFrame with one row for empty DataFrames
                df = pd.DataFrame({new_column_name: [basename]})
            else:
                # Use assign for non-empty DataFrames
                df = df.assign(**{new_column_name: basename})
        else:
            self.log.debug(f"No filename column required in table `{table}`.")

        return df

    # --------------------------------------------------------------
    def _apply_filename_data_processing_rules(self, key: str, value: str) -> str:
        """Apply the filename data processing rules to the value.

        Args:
            key (str): Key of the filename data.
            value (str): Value of the filename data.

        Returns:
            str: Processed value.
        """

        if key in self.config.filename_data_processing_rules:
            for rule in self.config.filename_data_processing_rules[key].keys():
                match rule:
                    case cm.REPLACE_KEY:
                        for replacement in self.config.filename_data_processing_rules[
                            key
                        ][cm.REPLACE_KEY]:
                            old_char = replacement[cm.OLD_KEY]
                            new_char = replacement[cm.NEW_KEY]
                            value = value.replace(old_char, new_char)

                    case cm.ADD_SUFFIX_KEY:
                        suffix = self.config.filename_data_processing_rules[key][
                            cm.ADD_SUFFIX_KEY
                        ]
                        value = f"{value}{suffix}"

                    case cm.ADD_PREFIX_KEY:
                        prefix = self.config.filename_data_processing_rules[key][
                            cm.ADD_PREFIX_KEY
                        ]
                        value = f"{prefix}{value}"
                    case _:
                        self.log.error(
                            f"Unknown rule '{rule}' in filename data processing rules. Ignoring"
                        )

        return value

    # --------------------------------------------------------------
    def _add_filename_data(
        self, df: pd.DataFrame, table: str, file: str
    ) -> pd.DataFrame:
        """Complement the data with metadata extracted from the filename using regex groups.

        Args:
            df: DataFrame into which the filename data may be added.
            table: Name of the table to be used as defined in the config file.
            file: The metadata file being processed

        Returns:
            pd.DataFrame: Updated DataFrame with the filename data
        """

        if self.config.filename_data_format is None:
            self.log.debug("No filename data format defined in the config file.")
            return df

        basename = os.path.basename(file)

        if table in self.config.filename_data_format.keys():
            # Get regex pattern for this table (already a compiled re.Pattern)
            re_formatting = self.config.filename_data_format[table]

            # Extract data from filename using compiled regex pattern
            match_result = re_formatting.match(basename)
            if not match_result:
                self.log.debug(
                    f"Filename '{basename}' doesn't match pattern for table '{table}'"
                )
                return df

            filename_data = match_result.groupdict()

            if not filename_data:
                self.log.debug(
                    f"No named groups matched in filename '{basename}' for table '{table}'"
                )
                return df

            # Assign each extracted group as a new column for all rows in the DataFrame
            # Prepare a dict with processed filename data
            processed_data = {
                key: self._apply_filename_data_processing_rules(key=key, value=value)
                for key, value in filename_data.items()
            }
            if df.empty:
                df = pd.DataFrame([processed_data])
            else:
                df = df.assign(**processed_data)

            self.log.debug(
                f"Added {len(filename_data)} metadata fields from filename to table '{table}'"
            )

        else:
            self.log.debug(
                f"No filename data format defined for table '{table}'. No metadata added from filename."
            )

        return df

    # --------------------------------------------------------------
    def read_reference_df(self) -> tuple[dict[str, pd.DataFrame], dict[str, list]]:
        """Read the most recently updated reference DataFrame from the list of catalog files.

        Args: None

        Returns:
            dict[str,pd.DataFrame]: Dictionary with the DataFrames containing various tables.
            dict[str,list]: Dictionary with the lists of columns for each table.
        """

        # find the newest file in the list of catalog files
        latest_time: float = 0.0
        latest_file: str = None
        ref_df: dict[str, pd.DataFrame] = {}
        ref_cols: dict[str, list] = {}

        for file in self.config.catalog_files:
            if os.path.isfile(file):
                if os.path.getmtime(file) > latest_time:
                    latest_time = os.path.getmtime(file)
                    latest_file = file

        if latest_file:
            self.log.info(f"Reference data loaded from file: {latest_file}")
            ref_df, ref_cols = self.read_metadata(
                file=latest_file,
                suggested_table=self.config.default_multiple_object_key,
            )

            for table, df in ref_df.items():
                if len(df.columns) == 0:
                    self.log.warning(
                        f"Table '{table}' in file '{latest_file}' does not contain valid data. A new table will be created."
                    )
                    for file in self.config.catalog_files:
                        self.file.trash_it(
                            file=file, overwrite=self.config.trash_data_overwrite
                        )
                        self.log.warning(
                            f"File '{file}' moved to trash as it contains no valid data."
                        )
        else:
            self.log.warning(
                "No reference data file found. Starting with a blank reference."
            )
            ref_df = {key: pd.DataFrame() for key in self.config.table_names}
            ref_cols = {key: [] for key in self.config.table_names}

        return ref_df, ref_cols

    # --------------------------------------------------------------
    def process_metadata_files(self, metadata_files: dict[str, set[str]]) -> None:
        """Process a set of metadata files and update the reference data file.

        Args:
            metadata_files (dict[str,set[str]]): Dictionary of files to process, keyed by table name.
            config (Config): Configuration object.
            log (logging.Logger): Logger object.

        Returns: None
        """

        files_to_move_to_store = []

        for table_associated_file, files in metadata_files.items():
            for file in files:
                new_data_df, column_in = self.read_metadata(
                    file=file, suggested_table=table_associated_file
                )

                self.log.info(f"Processing metadata file: {file}")

                # If data was loaded, put the file in the list to be moved to store, otherwise may move it to trash
                trash_file = True
                for df in new_data_df.values():
                    if not df.empty:
                        files_to_move_to_store.append(file)
                        trash_file = False
                        break

                if self.config.discard_invalid_data_files and trash_file:
                    self.file.trash_it(
                        file=file, overwrite=self.config.trash_data_overwrite
                    )
                    continue

                # Compute the new column order for the reference DataFrame
                self.ref_cols = self.merge_dicts(
                    new_dict=column_in, legacy_dict=self.ref_cols
                )

                # Update reference data with new data from the file
                self.update_reference_data(new_data_df=new_data_df, file=file)

        if files_to_move_to_store:
            if self.persist_reference():
                self.file.move_to_store(files_to_move_to_store)

                # Reset set of data files to ignore, since the reference data has been updated
                self.data_files_to_ignore = {
                    k: set() for k in self.config.data_file_regex.keys()
                }

    # --------------------------------------------------------------
    def process_data_files(self, files_to_process: dict[str, set[str]]) -> None:
        """Process the set of data files and update the reference metadata file, if necessary.

        Args:
            files_to_process (set[str]): List of pdf files to process.
            reference_df (pd.DataFrame): Reference data DataFrame.
            log (logging.Logger): Logger object.

        Returns: None
        """
        files_not_counted = {}

        for target_folder_key, file_set in files_to_process.items():
            if file_set is None or not file_set:
                continue

            self.log.info(f"Processing {len(file_set)} data files")

            files_found_in_ref = set()
            files_to_move_only = set()

            for file in file_set:
                self.log.debug(f"Processing data file: {file}")

                table_not_found = True

                for table in self.ref_df.keys():
                    if self.ref_df[table].empty:
                        continue

                    data_file_column = self.config.columns_data_filenames.get(table, [])

                    for column in data_file_column:
                        table_not_found = False

                        if column not in self.ref_df[table].columns:
                            self.log.warning(
                                f"Column '{column}' not found in table '{table}'. Skipping file '{file}'."
                            )
                            continue

                        match = self.ref_df[table][
                            self.ref_df[table][column].str.contains(
                                os.path.basename(file)
                            )
                        ]

                        if not match.empty:
                            for status_column in self.config.columns_data_published[
                                table
                            ]:
                                self.ref_df[table].loc[match.index, status_column] = (
                                    "True"
                                )
                                files_found_in_ref.add(file)

                if table_not_found:
                    self.log.debug(f"File '{file}' nota associated with metadata.")
                    files_to_move_only.add(file)
                    continue

            files_not_counted = file_set - files_found_in_ref

            if files_not_counted:
                self.data_files_to_ignore[target_folder_key] = files_not_counted
                self.log.warning(
                    f"Not all data files were considered. Leaving {len(files_not_counted)} in TEMP folder."
                )

            if files_found_in_ref:
                if self.persist_reference():
                    if self.file.publish_data_file(
                        files_found_in_ref, target_folder_key
                    ):
                        self.file.remove_file_list(files_found_in_ref)

            if files_to_move_only:
                if self.file.publish_data_file(files_to_move_only, target_folder_key):
                    self.file.remove_file_list(files_to_move_only)

    # --------------------------------------------------------------
    def persist_reference(self) -> bool:
        """Persist the reference DataFrame to the catalog file.

        Args: None

        Returns:
            bool: True if the reference data is saved successfully
        """

        df = {}
        for table in self.ref_df.keys():
            # sort the reference DataFrame by the columns defined in the config file
            df[table] = self.ref_df[table].sort_values(
                by=self.config.rows_sort_by[table][cm.SORT_BY_KEY],
                ascending=self.config.rows_sort_by[table][cm.ASCENDING_SORT_KEY],
                ignore_index=True,
            )

            # get selected columns in the defined order
            df[table] = df[table][self.ref_cols[table]]

        # loop through the target catalog files and save the reference data,
        # ensuring that at least one file is saved successfully before returning True
        save_at_least_one = False
        # TODO: #19 Instead of saving multiple files from the df, save one and copy to the remaining folders.
        for catalog_file in self.config.catalog_files:
            try:
                with pd.ExcelWriter(catalog_file, engine="openpyxl") as writer:
                    # Write each table to a separate sheet in the Excel file
                    for table in df.keys():
                        df[table].to_excel(
                            writer,
                            sheet_name=self.config.table_names[table],
                            index=False,
                        )

                self.log.info(f"Reference data file updated: {catalog_file}")
                save_at_least_one = True
            except Exception as e:
                self.log.error(f"Error saving reference data: {e}")

        if not save_at_least_one:
            self.log.error("No reference data file was saved. No changes were made.")

        return save_at_least_one
