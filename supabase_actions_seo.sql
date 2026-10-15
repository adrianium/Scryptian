-- Unique SEO content for the new Scryptian actions.
-- Apply in Supabase SQL editor. UPSERTs by id; safe to re-run.

-- 1. Compress PDF
insert into public.actions (id, title, description, long_description, features, tags, category, price, unit, price_per_unit, mode, entry, version, published, author)
values (
  'compress_pdf', 'Compress PDF',
  'Reduce a PDF file size by downsampling images and re-encoding content.',
  E'Compress PDF makes large PDF files dramatically smaller so they are faster to upload, email, and store. It downsamples embedded images to a standard 150 dpi and re-encodes the document streams, which removes the bulk of the size from scanned and image-heavy PDFs while keeping the layout and the text fully searchable.\n\nThis action runs entirely on your Windows device using Ghostscript — nothing is uploaded to a server and there is no per-use cost. Copy a PDF, press Ctrl+Alt, and the compressed file appears right next to the original.\n\nBest for scanned documents, photo-heavy reports, and any PDF that has grown too large to share. For already-optimized text-only PDFs, the action reports when no further reduction is possible.',
  ARRAY['Downsamples embedded images to 150 dpi','Keeps text searchable and selectable','Preserves the original page layout','Runs 100% locally with no upload','Free to use'],
  ARRAY['pdf','compress','reduce file size','optimize','ghostscript','local'],
  'File Compression', 0, 'page', 0, 'local', 'skill.py', '1.0.0', true, 'Scryptian'
)
on conflict (id) do update set
  title = excluded.title, description = excluded.description, long_description = excluded.long_description,
  features = excluded.features, tags = excluded.tags, category = excluded.category,
  price = excluded.price, unit = excluded.unit, price_per_unit = excluded.price_per_unit,
  mode = excluded.mode, version = excluded.version, published = excluded.published;

-- 2. Compress Image
insert into public.actions (id, title, description, long_description, features, tags, category, price, unit, price_per_unit, mode, entry, version, published, author)
values (
  'image_compress', 'Compress Image',
  'Shrink a photo file size with smart JPEG recompression.',
  E'Compress Image makes photos smaller so they upload and load faster. It recompresses PNG, WebP, and BMP images into an optimized JPEG at 80% quality and automatically downscales unusually large images, all without a visible loss of sharpness.\n\nEverything happens locally on your Windows machine with no cloud upload and no cost. Copy an image, press Ctrl+Alt, and the compressed copy is saved next to the original.\n\nUse it before sending images by email, uploading to a website, or freeing up disk space.',
  ARRAY['Converts to optimized JPEG','Auto-downscales oversized images','Keeps natural photo sharpness','Runs locally with no upload','Free to use'],
  ARRAY['image','compress','jpeg','photo','reduce size','local'],
  'File Compression', 0, '', 0, 'local', 'skill.py', '1.0.0', true, 'Scryptian'
)
on conflict (id) do update set
  title = excluded.title, description = excluded.description, long_description = excluded.long_description,
  features = excluded.features, tags = excluded.tags, category = excluded.category,
  price = excluded.price, unit = excluded.unit, price_per_unit = excluded.price_per_unit,
  mode = excluded.mode, version = excluded.version, published = excluded.published;

-- 3. Compress Video (Light)
insert into public.actions (id, title, description, long_description, features, tags, category, price, unit, price_per_unit, mode, entry, version, published, author)
values (
  'video_compress_light', 'Compress Video (Light)',
  'Compress a video with minimal quality loss — near-lossless output.',
  E'Compress Video (Light) shrinks a video file while keeping quality as close to the original as possible. It re-encodes to H.264 with a low CRF, so the result is nearly indistinguishable from the source — ideal when you need a smaller file but cannot afford visible artifacts.\n\nRuns locally with ffmpeg on your Windows device, with no upload and no cost. Copy a video, press Ctrl+Alt, and the compressed MP4 is saved beside the original.\n\nChoose Light when quality matters more than size.',
  ARRAY['Near-lossless H.264 encoding','Keeps original visual quality','AAC audio at 128k','Runs locally with ffmpeg','Free to use'],
  ARRAY['video','compress','near-lossless','h264','ffmpeg','local'],
  'Video Compression', 0, 'second', 0, 'local', 'skill.py', '1.0.0', true, 'Scryptian'
)
on conflict (id) do update set
  title = excluded.title, description = excluded.description, long_description = excluded.long_description,
  features = excluded.features, tags = excluded.tags, category = excluded.category,
  price = excluded.price, unit = excluded.unit, price_per_unit = excluded.price_per_unit,
  mode = excluded.mode, version = excluded.version, published = excluded.published;

-- 4. Compress Video (Balanced)
insert into public.actions (id, title, description, long_description, features, tags, category, price, unit, price_per_unit, mode, entry, version, published, author)
values (
  'video_compress_balanced', 'Compress Video (Balanced)',
  'Compress a video with a good balance of file size and quality.',
  E'Compress Video (Balanced) is the middle ground: it re-encodes video to H.264 at a balanced CRF that meaningfully reduces file size while preserving a clean, watchable picture. Most people get the best size-to-quality trade-off from this setting.\n\nRuns locally with ffmpeg, with no upload and no cost. Copy a video, press Ctrl+Alt, and the compressed MP4 appears next to the original.\n\nChoose Balanced for everyday sharing where you want a smaller file without obvious quality loss.',
  ARRAY['Balanced H.264 CRF','Great size-to-quality ratio','AAC audio at 128k','Runs locally with ffmpeg','Free to use'],
  ARRAY['video','compress','balanced','h264','ffmpeg','local'],
  'Video Compression', 0, 'second', 0, 'local', 'skill.py', '1.0.0', true, 'Scryptian'
)
on conflict (id) do update set
  title = excluded.title, description = excluded.description, long_description = excluded.long_description,
  features = excluded.features, tags = excluded.tags, category = excluded.category,
  price = excluded.price, unit = excluded.unit, price_per_unit = excluded.price_per_unit,
  mode = excluded.mode, version = excluded.version, published = excluded.published;

-- 5. Compress Video (Strong)
insert into public.actions (id, title, description, long_description, features, tags, category, price, unit, price_per_unit, mode, entry, version, published, author)
values (
  'video_compress_strong', 'Compress Video (Strong)',
  'Compress a video to the smallest possible file size.',
  E'Compress Video (Strong) squeezes a video down to the smallest size possible. It re-encodes to H.264 with an aggressive CRF, trading some quality for maximum space savings — perfect for email attachments, messaging apps, and long videos you just need to store.\n\nRuns locally with ffmpeg, with no upload and no cost. Copy a video, press Ctrl+Alt, and the compressed MP4 is saved next to the original.\n\nChoose Strong when size matters more than quality.',
  ARRAY['Aggressive H.264 compression','Smallest possible file size','AAC audio at 128k','Runs locally with ffmpeg','Free to use'],
  ARRAY['video','compress','smallest size','h264','ffmpeg','local'],
  'Video Compression', 0, 'second', 0, 'local', 'skill.py', '1.0.0', true, 'Scryptian'
)
on conflict (id) do update set
  title = excluded.title, description = excluded.description, long_description = excluded.long_description,
  features = excluded.features, tags = excluded.tags, category = excluded.category,
  price = excluded.price, unit = excluded.unit, price_per_unit = excluded.price_per_unit,
  mode = excluded.mode, version = excluded.version, published = excluded.published;

-- 6. Extract Audio
insert into public.actions (id, title, description, long_description, features, tags, category, price, unit, price_per_unit, mode, entry, version, published, author)
values (
  'extract_audio', 'Extract Audio',
  'Pull the audio track out of any video as an M4A file.',
  E'Extract Audio takes the soundtrack out of a video file and saves it as a compact M4A (AAC) file — no video, just the audio. It is perfect for turning a talk, interview, podcast, or music video into an audio file you can listen to anywhere.\n\nRuns locally with ffmpeg on your Windows device, with no upload and no cost. Copy a video, press Ctrl+Alt, and the M4A is saved beside the original.\n\nUse it to create audio from video lectures, extract music, or make a file that plays on any audio player.',
  ARRAY['Extracts audio as M4A (AAC 192k)','Removes the video track','Keeps the full audio duration','Runs locally with ffmpeg','Free to use'],
  ARRAY['audio','extract','m4a','video to audio','ffmpeg','local'],
  'Audio', 0, 'second', 0, 'local', 'skill.py', '1.0.0', true, 'Scryptian'
)
on conflict (id) do update set
  title = excluded.title, description = excluded.description, long_description = excluded.long_description,
  features = excluded.features, tags = excluded.tags, category = excluded.category,
  price = excluded.price, unit = excluded.unit, price_per_unit = excluded.price_per_unit,
  mode = excluded.mode, version = excluded.version, published = excluded.published;

-- 7. Merge PDF
insert into public.actions (id, title, description, long_description, features, tags, category, price, unit, price_per_unit, mode, entry, version, published, author)
values (
  'merge_pdf', 'Merge PDF',
  'Combine all PDFs in a folder into a single document.',
  E'Merge PDF combines multiple PDF files from one folder into a single, ordered document. It reads every PDF in the folder, sorts them by name, and writes a merged.pdf — ideal for combining chapters, invoices, or scanned pages into one file.\n\nRuns locally on your Windows device with no upload and no cost. Put the PDFs you want to merge into a folder, copy any one of them, press Ctrl+Alt, and the merged document is saved in that same folder.\n\nUse it to consolidate reports, contracts, or multi-part documents before sharing or archiving.',
  ARRAY['Merges every PDF in a folder','Sorts pages by file name','Preserves page order and content','Runs locally with no upload','Free to use'],
  ARRAY['pdf','merge','combine','documents','local'],
  'PDF Tools', 0, '', 0, 'local', 'skill.py', '1.0.0', true, 'Scryptian'
)
on conflict (id) do update set
  title = excluded.title, description = excluded.description, long_description = excluded.long_description,
  features = excluded.features, tags = excluded.tags, category = excluded.category,
  price = excluded.price, unit = excluded.unit, price_per_unit = excluded.price_per_unit,
  mode = excluded.mode, version = excluded.version, published = excluded.published;

-- 8. PDF to JPG
insert into public.actions (id, title, description, long_description, features, tags, category, price, unit, price_per_unit, mode, entry, version, published, author)
values (
  'pdf_to_jpg', 'PDF to JPG',
  'Convert every PDF page into a high-resolution JPG image.',
  E'PDF to JPG renders each page of a PDF into a separate high-resolution JPG at 300 dpi, so text and graphics stay sharp. The images are saved into their own folder next to the original PDF, named page_1.jpg, page_2.jpg, and so on.\n\nRuns locally with Ghostscript on your Windows device, with no upload and no cost. Copy a PDF, press Ctrl+Alt, and a folder of page images is created beside it.\n\nUse it to turn PDF pages into images for slides, editing, thumbnails, or sharing individual pages.',
  ARRAY['Renders at 300 dpi for sharp text','One JPG per PDF page','Saves into a dedicated folder','Runs locally with Ghostscript','Free to use'],
  ARRAY['pdf','jpg','convert','render','image','local'],
  'PDF Tools', 0, 'page', 0, 'local', 'skill.py', '1.0.0', true, 'Scryptian'
)
on conflict (id) do update set
  title = excluded.title, description = excluded.description, long_description = excluded.long_description,
  features = excluded.features, tags = excluded.tags, category = excluded.category,
  price = excluded.price, unit = excluded.unit, price_per_unit = excluded.price_per_unit,
  mode = excluded.mode, version = excluded.version, published = excluded.published;

-- 9. JPG to PDF
insert into public.actions (id, title, description, long_description, features, tags, category, price, unit, price_per_unit, mode, entry, version, published, author)
values (
  'jpg_to_pdf', 'JPG to PDF',
  'Turn an image into a PDF document.',
  E'JPG to PDF converts a single image (JPG, PNG, WebP, or BMP) into a clean PDF document. It places the image on a page at 150 dpi, ready to share, print, or archive as a standard document.\n\nRuns locally on your Windows device with no upload and no cost. Copy an image, press Ctrl+Alt, and the PDF is saved next to the original.\n\nUse it to turn a photo, screenshot, or scan into a portable document.',
  ARRAY['Converts an image to PDF','Supports JPG, PNG, WebP, BMP','Produces a standard page','Runs locally with no upload','Free to use'],
  ARRAY['image','pdf','convert','document','local'],
  'PDF Tools', 0, '', 0, 'local', 'skill.py', '1.0.0', true, 'Scryptian'
)
on conflict (id) do update set
  title = excluded.title, description = excluded.description, long_description = excluded.long_description,
  features = excluded.features, tags = excluded.tags, category = excluded.category,
  price = excluded.price, unit = excluded.unit, price_per_unit = excluded.price_per_unit,
  mode = excluded.mode, version = excluded.version, published = excluded.published;

-- 10. Remove Background (Video)
insert into public.actions (id, title, description, long_description, features, tags, category, price, unit, price_per_unit, mode, entry, version, published, author)
values (
  'remove_background_video', 'Remove Background (Video)',
  'Remove the background from a video with AI, on a green screen.',
  E'Remove Background (Video) uses AI video matting to cut the subject out of a video and place it on a clean green screen, ready for chroma-key compositing in any editor. It handles motion and keeps the cut stable across frames, so hair and edges stay clean.\n\nRuns in the cloud with a state-of-the-art matting model. Copy a video, press Ctrl+Alt, and the green-screen MP4 is saved next to the original.\n\nUse it to isolate a person from a busy background for thumbnails, intros, or video editing.',
  ARRAY['AI video matting (RVM)','Outputs on a green screen','Stable cut across frames','Handles people and motion','Cloud processing'],
  ARRAY['video','background removal','green screen','ai','matting'],
  'Video Editing', 0, 'megapixel', 200, 'cloud', 'skill.py', '1.0.0', true, 'Scryptian'
)
on conflict (id) do update set
  title = excluded.title, description = excluded.description, long_description = excluded.long_description,
  features = excluded.features, tags = excluded.tags, category = excluded.category,
  price = excluded.price, unit = excluded.unit, price_per_unit = excluded.price_per_unit,
  mode = excluded.mode, version = excluded.version, published = excluded.published;

-- 11. Download Video from Web
insert into public.actions (id, title, description, long_description, features, tags, category, price, unit, price_per_unit, mode, entry, version, published, author)
values (
  'download_video_from_web', 'Download Video from Web',
  'Download a web video as MP4, up to 1080p.',
  E'Download Video from Web saves a video from any of 1,600+ sites — YouTube, TikTok, Instagram, Facebook, X, and more — as an MP4 file. It always targets 1080p; if the source is lower resolution, it takes the highest available.\n\nThe download is fetched through a hosted service, so your device never hits rate limits. Copy a link, press Ctrl+Alt, and the MP4 is saved to your Downloads folder.\n\nUse it to keep an offline copy of a tutorial, clip, or any web video.',
  ARRAY['Works with 1,600+ sites','Targets 1080p quality','Saves as MP4','No local rate limits','Handles YouTube, TikTok, Instagram'],
  ARRAY['video','download','mp4','youtube','tiktok','web'],
  'Media Download', 0, '', 0, 'cloud', 'skill.py', '1.0.0', true, 'Scryptian'
)
on conflict (id) do update set
  title = excluded.title, description = excluded.description, long_description = excluded.long_description,
  features = excluded.features, tags = excluded.tags, category = excluded.category,
  price = excluded.price, unit = excluded.unit, price_per_unit = excluded.price_per_unit,
  mode = excluded.mode, version = excluded.version, published = excluded.published;

-- 12. Download Audio from Web Video
insert into public.actions (id, title, description, long_description, features, tags, category, price, unit, price_per_unit, mode, entry, version, published, author)
values (
  'download_audio_from_web_video', 'Download Audio from Web Video',
  'Download the audio from a web video as MP3.',
  E'Download Audio from Web Video extracts the audio from any web video — YouTube, TikTok, Instagram, and 1,600+ other sites — and saves it as an MP3 file. No video, just the audio, ready for any music player or podcast app.\n\nThe download is fetched through a hosted service, so your device never hits rate limits. Copy a link, press Ctrl+Alt, and the MP3 is saved to your Downloads folder.\n\nUse it to grab a song, a talk, or any video''s audio for offline listening.',
  ARRAY['Works with 1,600+ sites','Saves as MP3 audio','Strips the video track','No local rate limits','Handles YouTube, TikTok, Instagram'],
  ARRAY['audio','download','mp3','youtube','tiktok','web'],
  'Media Download', 0, '', 0, 'cloud', 'skill.py', '1.0.0', true, 'Scryptian'
)
on conflict (id) do update set
  title = excluded.title, description = excluded.description, long_description = excluded.long_description,
  features = excluded.features, tags = excluded.tags, category = excluded.category,
  price = excluded.price, unit = excluded.unit, price_per_unit = excluded.price_per_unit,
  mode = excluded.mode, version = excluded.version, published = excluded.published;