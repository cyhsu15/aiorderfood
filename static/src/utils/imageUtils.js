/**
 * 圖片格式轉換工具
 * 將圖片路徑轉換為 WebP 格式
 */

/**
 * 將圖片路徑轉換為 WebP 格式
 * @param {string} imagePath - 原始圖片路徑
 * @returns {string} WebP 格式的圖片路徑
 *
 * 範例：
 * toWebP('/images/dish/123.jpeg') => '/images/dish/123.webp'
 * toWebP('/images/dish/123.png') => '/images/dish/123.webp'
 * toWebP('/images/default.png') => '/images/default.png' (保留 default.png)
 */
export function toWebP(imagePath) {
  if (!imagePath || typeof imagePath !== 'string') {
    return imagePath
  }

  // 保留特定 PNG 文件不轉換
  const excludeFiles = [
    'default.png',
    'banner.png',
    'customer-avatar.png',
    'logo.png'
  ]

  if (excludeFiles.some(file => imagePath.includes(file))) {
    return imagePath
  }

  // 將 .jpeg, .jpg, .png 替換為 .webp
  return imagePath.replace(/\.(jpeg|jpg|png)$/i, '.webp')
}

/**
 * 檢查瀏覽器是否支援 WebP
 * @returns {Promise<boolean>}
 */
export function checkWebPSupport() {
  return new Promise((resolve) => {
    const webP = new Image()
    webP.onload = webP.onerror = () => {
      resolve(webP.height === 2)
    }
    webP.src = 'data:image/webp;base64,UklGRjoAAABXRUJQVlA4IC4AAACyAgCdASoCAAIALmk0mk0iIiIiIgBoSygABc6WWgAA/veff/0PP8bA//LwYAAA'
  })
}
