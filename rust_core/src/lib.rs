use pyo3::prelude::*;
use pyo3::types::PyList;

mod epg_parser;
mod fuzzy_search;
mod image_optimizer;
mod m3u_parser;

#[pyfunction]
#[pyo3(signature = (content, progress_callback=None))]
fn parse_m3u_raw_text<'py>(
    py: Python<'py>,
    content: &str,
    progress_callback: Option<&Bound<'py, PyAny>>,
) -> PyResult<Bound<'py, PyList>> {
    m3u_parser::parse_m3u_raw(py, content, progress_callback)
}

#[pyfunction]
#[pyo3(signature = (file_path, progress_callback=None))]
fn parse_m3u_raw_file<'py>(
    py: Python<'py>,
    file_path: &str,
    progress_callback: Option<&Bound<'py, PyAny>>,
) -> PyResult<Bound<'py, PyList>> {
    let content = m3u_parser::read_m3u_file(file_path)?;
    m3u_parser::parse_m3u_raw(py, &content, progress_callback)
}

#[pyfunction]
fn parse_xmltv_date(date_str: &str) -> String {
    epg_parser::parse_xmltv_date(date_str)
}

#[pyfunction]
#[pyo3(signature = (file_path, batch_callback, batch_size=2000, progress_callback=None))]
fn parse_epg_file<'py>(
    py: Python<'py>,
    file_path: &str,
    batch_callback: &Bound<'py, PyAny>,
    batch_size: usize,
    progress_callback: Option<&Bound<'py, PyAny>>,
) -> PyResult<usize> {
    epg_parser::parse_epg_file(py, file_path, batch_size, batch_callback, progress_callback)
}

#[pyfunction]
#[pyo3(signature = (data, batch_callback, batch_size=2000, progress_callback=None))]
fn parse_epg_bytes<'py>(
    py: Python<'py>,
    data: &[u8],
    batch_callback: &Bound<'py, PyAny>,
    batch_size: usize,
    progress_callback: Option<&Bound<'py, PyAny>>,
) -> PyResult<usize> {
    epg_parser::parse_epg_bytes(py, data, batch_size, batch_callback, progress_callback)
}

#[pyfunction]
fn update_search_index(
    raw_items: Vec<(i64, i64, String, String, String, String, bool, bool)>,
) {
    fuzzy_search::update_search_index(raw_items);
}

#[pyfunction]
fn is_search_index_ready() -> bool {
    fuzzy_search::is_index_ready()
}

#[pyfunction]
fn get_search_index_size() -> usize {
    fuzzy_search::index_size()
}

#[pyfunction]
fn clear_search_index() {
    fuzzy_search::clear_index();
}

#[pyfunction]
#[pyo3(signature = (query, playlist_id=None, stream_type=None, group_title=None, favorites_only=false, only_enabled=true, limit=50000, offset=0))]
fn search_channel_ids(
    query: &str,
    playlist_id: Option<i64>,
    stream_type: Option<&str>,
    group_title: Option<&str>,
    favorites_only: bool,
    only_enabled: bool,
    limit: usize,
    offset: usize,
) -> Vec<i64> {
    fuzzy_search::search_channels(
        query,
        playlist_id,
        stream_type,
        group_title,
        favorites_only,
        only_enabled,
        limit,
        offset,
    )
}

#[pyfunction]
fn optimize_and_cache_image(raw_bytes: &[u8], disk_path: &str) -> PyResult<Vec<u8>> {
    image_optimizer::optimize_and_save_image(raw_bytes, disk_path)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e))
}

#[pyfunction]
fn is_rust_core_active() -> bool {
    true
}

#[pymodule]
fn iptv_core_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(parse_m3u_raw_text, m)?)?;
    m.add_function(wrap_pyfunction!(parse_m3u_raw_file, m)?)?;
    m.add_function(wrap_pyfunction!(parse_xmltv_date, m)?)?;
    m.add_function(wrap_pyfunction!(parse_epg_file, m)?)?;
    m.add_function(wrap_pyfunction!(parse_epg_bytes, m)?)?;
    m.add_function(wrap_pyfunction!(update_search_index, m)?)?;
    m.add_function(wrap_pyfunction!(is_search_index_ready, m)?)?;
    m.add_function(wrap_pyfunction!(get_search_index_size, m)?)?;
    m.add_function(wrap_pyfunction!(clear_search_index, m)?)?;
    m.add_function(wrap_pyfunction!(search_channel_ids, m)?)?;
    m.add_function(wrap_pyfunction!(optimize_and_cache_image, m)?)?;
    m.add_function(wrap_pyfunction!(is_rust_core_active, m)?)?;
    Ok(())
}
