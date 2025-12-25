export const truncate = (text, max = 20) =>
  !text ? "" : text.length > max ? text.slice(0, max) + "..." : text;

export const formatFileSize = (bytes) => {
  if (!bytes) return "";
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return (bytes / Math.pow(1024, i)).toFixed(1) + " " + sizes[i];
};

export const isImage = (filename) =>
  /\.(jpg|jpeg|png|gif|webp)$/i.test(filename);