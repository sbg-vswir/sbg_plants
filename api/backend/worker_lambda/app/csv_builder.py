import io
import pandas as pd


def build_spectral_csv(rows: list, col_descriptions: list, spectral_metadata: dict) -> pd.DataFrame:
    """
    Build a single-header DataFrame for a spectral export (radiance or reflectance).

    All non-spectral columns are passed through as-is from the query result.
    The spectral array column is exploded into individual band columns named
    'wavelength|fwhm' (e.g. '383.8840|5.7398').

    Args:
        rows:              Raw rows from the psycopg2 cursor.
        col_descriptions:  cursor.description — used to identify column names/indexes.
        spectral_metadata: Dict with keys wavelength_center, fwhm, spectral_column.
    """
    wavelength_center = spectral_metadata['wavelength_center']
    fwhm_vals         = spectral_metadata['fwhm']
    spectral_col      = spectral_metadata['spectral_column']  # 'radiance' or 'reflectance'

    col_names = [desc[0] for desc in col_descriptions]
    spec_idx  = col_names.index(spectral_col)
    fixed_cols = [name for name in col_names if name != spectral_col]
    fixed_idxs = [i for i, name in enumerate(col_names) if name != spectral_col]

    spectral_headers = [f"{wl:.4f}|{fw:.4f}" for wl, fw in zip(wavelength_center, fwhm_vals)]
    headers = fixed_cols + spectral_headers

    data = []
    for row in rows:
        fixed_vals    = [row[i] for i in fixed_idxs]
        spectral_vals = list(row[spec_idx])
        data.append(fixed_vals + spectral_vals)

    return pd.DataFrame(data, columns=headers)


def build_standard_csv(rows: list, col_descriptions: list) -> pd.DataFrame:
    """Plain CSV — column names taken directly from the query result descriptor."""
    return pd.DataFrame(rows, columns=[desc[0] for desc in col_descriptions])


def dataframe_to_csv_buffer(df: pd.DataFrame, write_header: bool) -> io.StringIO:
    """Serialise a DataFrame to a StringIO buffer ready for S3 upload."""
    buffer = io.StringIO()
    df.to_csv(buffer, index=False, header=write_header)
    buffer.seek(0)
    return buffer
