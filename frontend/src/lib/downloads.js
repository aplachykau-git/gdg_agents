export async function downloadDirectFile(url, suggestedFilename) {
  if (!url) return;
  const filename = suggestedFilename || url.split('/').pop()?.split('?')[0] || 'media_asset';
  if (url.startsWith('file://')) {
    window.location.assign(url);
    return;
  }

  try {
    const separator = url.includes('?') ? '&' : '?';
    const downloadUrl = `${url}${separator}dl=1&_t=${Date.now()}`;
    const res = await fetch(downloadUrl, { mode: 'cors' });
    if (!res.ok) {
      throw new Error(`Server returned HTTP status ${res.status}`);
    }
    const blob = await res.blob();
    const blobUrl = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = blobUrl;
    link.download = filename;
    link.style.display = 'none';
    document.body.appendChild(link);
    link.click();
    setTimeout(() => {
      document.body.removeChild(link);
      window.URL.revokeObjectURL(blobUrl);
    }, 2000);
  } catch (err) {
    console.warn('Direct blob fetch failed:', err);
    // If it's a relative /results/ path, try direct download anchor
    if (url.startsWith('/results/') || url.startsWith('http')) {
      const fallbackLink = document.createElement('a');
      fallbackLink.href = url;
      fallbackLink.download = filename;
      fallbackLink.target = '_blank';
      fallbackLink.rel = 'noopener noreferrer';
      fallbackLink.click();
    } else {
      alert(`Could not download file: ${err.message || 'File not found'}`);
    }
  }
}
