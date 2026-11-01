use image::imageops::FilterType;
use image::{GenericImageView, ImageFormat};
use std::fs;
use std::io::Cursor;
use std::path::Path;

pub fn optimize_and_save_image(raw_bytes: &[u8], disk_path_str: &str) -> Result<Vec<u8>, String> {
    let img = image::load_from_memory(raw_bytes).map_err(|e| e.to_string())?;
    let (w, h) = img.dimensions();
    if w == 0 || h == 0 {
        return Err("Dimensions invalides".to_string());
    }

    let has_alpha = img.color().has_alpha();

    // 1. Calcul des dimensions cibles
    let (max_w, max_h) = if has_alpha {
        (320, 320)
    } else if w > h {
        (1280, 720)
    } else {
        (400, 600)
    };

    // Redimensionnement bilinéaire rapide (équivalent SmoothTransformation de Qt)
    let processed_img = if w > max_w || h > max_h {
        img.resize(max_w, max_h, FilterType::Triangle)
    } else {
        img
    };

    // 2. Encodage unique en mémoire
    let mut out_bytes = Vec::with_capacity(32 * 1024);

    if has_alpha {
        let mut cursor = Cursor::new(&mut out_bytes);
        let _ = processed_img.write_to(&mut cursor, ImageFormat::Png);
    } else {
        let rgb_img = processed_img.into_rgb8();
        let mut cursor = Cursor::new(&mut out_bytes);
        let mut enc = image::codecs::jpeg::JpegEncoder::new_with_quality(&mut cursor, 85);
        let _ = enc.encode(
            rgb_img.as_raw(),
            rgb_img.width(),
            rgb_img.height(),
            image::ExtendedColorType::Rgb8,
        );
    }

    // 3. Écriture directe des octets encodés sur le disque
    let disk_path = Path::new(disk_path_str);
    if let Some(parent) = disk_path.parent() {
        let _ = fs::create_dir_all(parent);
    }
    let _ = fs::write(disk_path, &out_bytes);

    Ok(out_bytes)
}
