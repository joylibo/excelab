document.addEventListener('DOMContentLoaded', function() {
    
    // --- 定义基地址 ---
    const API_BASE_URL = ''; // 空字符串表示相对路径，请求会发送到当前域名

    // --- 日志和工具函数 ---
    function logEvent(message) { console.log(`[EVENT] ${message}`); }
    function showError(element, message) { 
        element.textContent = message;
        element.style.display = 'block'; 
    }
    function escapeHtml(unsafe) {
        return unsafe
             .replace(/&/g, "&amp;")
             .replace(/</g, "&lt;")
             .replace(/>/g, "&gt;")
             .replace(/"/g, "&quot;")
             .replace(/'/g, "&#039;");
    }
    function formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
    function simulateProgress(progressElement, duration) {
        let width = 0;
        const interval = duration / 100;
        const id = setInterval(() => {
            if (width >= 95) {
                clearInterval(id);
            } else {
                width++;
                progressElement.style.width = width + '%';
            }
        }, interval);
        return id;
    }

    // --- 1. 选项卡切换功能 ---
    document.querySelectorAll('.tab-nav-container').forEach(container => {
        container.addEventListener('click', (e) => {
            if (e.target.classList.contains('tab-button')) {
                const tab = e.target;

                // 只在当前容器内查找 tab-button 和 tab-pane
                const buttons = container.querySelectorAll('.tab-button');
                const panes = container.closest('.page-section').querySelectorAll('.tab-pane');

                // 移除当前容器内所有按钮的 active 类
                buttons.forEach(btn => btn.classList.remove('active'));
                // 添加当前按钮的 active 类
                tab.classList.add('active');

                // 获取目标 tab-pane ID
                const tabId = tab.getAttribute('data-tab');

                // 移除当前模块内所有 tab-pane 的 active 类
                panes.forEach(pane => pane.classList.remove('active'));
                // 显示目标 tab-pane
                const targetPane = document.getElementById(tabId);
                if (targetPane) {
                    targetPane.classList.add('active');
                }

                logEvent(`切换到 ${tab.textContent} 功能`);
            }
        });
    });
        
    // --- 2. 文件上传区域交互 ---
    const uploadAreas = document.querySelectorAll('.file-upload-wrapper');
    uploadAreas.forEach(area => {
        const input = area.querySelector('.file-input');
        
        area.addEventListener('dragover', (e) => { e.preventDefault(); area.classList.add('drag-over'); });
        area.addEventListener('dragleave', () => area.classList.remove('drag-over'));
        area.addEventListener('drop', (e) => {
            e.preventDefault();
            area.classList.remove('drag-over');
            input.files = e.dataTransfer.files;
            logEvent(`拖拽添加了 ${e.dataTransfer.files.length} 个文件`);
            handleFiles(input.files, input.id);
        });
        
        input.addEventListener('change', (e) => {
            logEvent(`选择了 ${e.target.files.length} 个文件`);
            handleFiles(e.target.files, input.id);
        });
    });

    // --- 3. 核心文件处理和API调用逻辑 ---

    // 处理上传的文件
    function handleFiles(files, inputId) {
        const prefix = inputId.split('-')[0];
        const fileList = document.getElementById(`${prefix}-file-list`);
        const submitButton = document.getElementById(`${prefix}-button`);
        
        fileList.innerHTML = ''; 
        
        if (files.length > 0) {
            const fileArray = Array.from(files);
            fileArray.forEach((file, i) => {
                const fileItem = document.createElement('div');
                fileItem.className = 'file-item';
                fileItem.innerHTML = `
                    <div class="file-name">${escapeHtml(file.name)}</div>
                    <div class="file-size">${formatFileSize(file.size)}</div>
                    <div class="file-remove" data-index="${i}"><i class="fas fa-times"></i></div>
                `;
                fileList.appendChild(fileItem);
            });
            
            submitButton.disabled = false;
            
            document.querySelectorAll(`#${prefix}-file-list .file-remove`).forEach(btn => {
                btn.addEventListener('click', (e) => {
                    e.stopPropagation(); 
                    const indexToRemove = parseInt(btn.getAttribute('data-index'));
                    logEvent(`移除文件索引: ${indexToRemove}`);
                    
                    const input = document.getElementById(`${prefix}-file-input`);
                    const dataTransfer = new DataTransfer();
                    Array.from(input.files)
                         .filter((_, i) => i !== indexToRemove)
                         .forEach(file => dataTransfer.items.add(file));
                    
                    input.files = dataTransfer.files;
                    handleFiles(input.files, input.id);
                });
            });
            
            if (prefix === 'split' && files.length > 0) {
                getColumnsForSplit(files[0]);
            }
        } else {
            submitButton.disabled = true;
            if (prefix === 'split') {
                const select = document.getElementById('split-column');
                select.disabled = true;
                select.innerHTML = '<option value="">请先上传文件</option>';
            }
        }
    }

    // 获取拆分文件的列名
    async function getColumnsForSplit(file) {
        const select = document.getElementById('split-column');
        const errorElement = document.getElementById('split-error');
        select.disabled = true;
        select.innerHTML = '<option value="">正在获取列名...</option>';
        logEvent('开始获取列名');
        try {
            const formData = new FormData();
            formData.append('file', file);
            const response = await fetch(`${API_BASE_URL}/api/split/columns`, {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                 const errorData = await response.json().catch(() => ({}));
                 throw new Error(errorData.detail || `获取列名失败 (${response.status})`);
            }

            const data = await response.json();
            const columns = data.columns;
            select.innerHTML = '<option value="">请选择拆分依据列</option>';
            columns.forEach(col => {
                const option = document.createElement('option');
                option.value = col;
                option.textContent = col;
                select.appendChild(option);
            });
            select.disabled = false;
            logEvent(`获取到 ${columns.length} 个列名`);
        } catch (error) {
            select.innerHTML = '<option value="">获取列名失败</option>';
            showError(errorElement, error.message);
            logEvent('获取列名失败: ' + error.message);
        }
    }
        
    // 合并功能提交
    document.getElementById('merge-button').addEventListener('click', async (e) => {
        e.preventDefault();
        const prefix = 'merge';
        const fileInput = document.getElementById(`${prefix}-file-input`);
        const loader = document.getElementById(`${prefix}-loader`);
        const progress = document.getElementById(`${prefix}-progress`);
        const errorElement = document.getElementById(`${prefix}-error`);
        const successElement = document.getElementById(`${prefix}-success`);
        const preview = document.getElementById(`${prefix}-preview`);
        const previewContent = document.getElementById('merge-preview-content');
        const downloadBtn = document.getElementById('merge-download');
        const mergeMode = document.querySelector('input[name="merge_mode"]:checked').value;

        if (fileInput.files.length === 0) { showError(errorElement, '请先上传文件'); return; }

        preview.style.display = 'none';
        errorElement.style.display = 'none';
        successElement.style.display = 'none';
        loader.style.display = 'block';
        progress.style.width = '0%';
        logEvent('开始请求合并预览...');

        const formData = new FormData();
        for (let i = 0; i < fileInput.files.length; i++) { formData.append('files', fileInput.files[i]); }
        formData.append('merge_mode', mergeMode);

        try {
            let progressInterval = simulateProgress(progress, 1500);
            const previewResponse = await fetch(`${API_BASE_URL}/api/merge/preview`, { method: 'POST', body: formData });
            clearInterval(progressInterval);
            progress.style.width = '100%';

            if (!previewResponse.ok) {
                const errorData = await previewResponse.json().catch(() => ({}));
                throw new Error(errorData.detail || `预览请求失败 (${previewResponse.status})`);
            }

            const previewData = await previewResponse.json();
            logEvent('预览数据获取成功');

            if (previewData.data && previewData.data.length > 0 && previewData.columns) {
                let tableHTML = '<table><thead><tr>';
                previewData.columns.forEach(col => { tableHTML += `<th>${escapeHtml(col)}</th>`; });
                tableHTML += '</tr></thead><tbody>';
                previewData.data.forEach(row => {
                    tableHTML += '<tr>';
                    previewData.columns.forEach(col => {
                        const cellValue = row[col] != null ? row[col] : "";
                        tableHTML += `<td>${escapeHtml(String(cellValue))}</td>`;
                    });
                    tableHTML += '</tr>';
                });
                tableHTML += '</tbody></table>';
                previewContent.innerHTML = tableHTML;
            } else {
                previewContent.innerHTML = '<p>合并结果为空或无法生成预览。</p>';
            }

            loader.style.display = 'none';
            successElement.textContent = `成功合并了 ${fileInput.files.length} 个文件！预览已生成。`;
            successElement.style.display = 'block';
            preview.style.display = 'block';

            downloadBtn.onclick = async function(event) {
                event.preventDefault();
                logEvent('开始下载合并文件...');
                loader.style.display = 'block';
                progress.style.width = '0%';
                errorElement.style.display = 'none';
                successElement.style.display = 'none';
                let downloadProgressInterval = simulateProgress(progress, 2000);

                try {
                    const downloadResponse = await fetch(`${API_BASE_URL}/api/merge`, { method: 'POST', body: formData });
                    clearInterval(downloadProgressInterval);
                    progress.style.width = '100%';

                    if (!downloadResponse.ok) {
                        const errorData = await downloadResponse.json().catch(() => ({}));
                        throw new Error(errorData.detail || `下载请求失败 (${downloadResponse.status})`);
                    }

                    const blob = await downloadResponse.blob();
                    const url = window.URL.createObjectURL(blob);
                    const tempLink = document.createElement('a');
                    tempLink.href = url;
                    tempLink.download = 'merged_pro.xlsx';
                    document.body.appendChild(tempLink);
                    tempLink.click();
                    document.body.removeChild(tempLink);
                    window.URL.revokeObjectURL(url);

                    loader.style.display = 'none';
                    successElement.textContent = '文件下载成功！';
                    successElement.style.display = 'block';
                    logEvent('合并文件下载成功');
                } catch (downloadError) {
                     loader.style.display = 'none';
                     showError(errorElement, `下载失败: ${downloadError.message}`);
                     logEvent('下载失败: ' + downloadError.message);
                }
            };
        } catch (error) {
            loader.style.display = 'none';
            showError(errorElement, error.message);
            logEvent('合并预览请求失败: ' + error.message);
        }
    });

    // 拆分功能提交
    document.getElementById('split-button').addEventListener('click', async (e) => {
        e.preventDefault();
        const prefix = 'split';
        const fileInput = document.getElementById(`${prefix}-file-input`);
        const loader = document.getElementById(`${prefix}-loader`);
        const progress = document.getElementById(`${prefix}-progress`);
        const errorElement = document.getElementById(`${prefix}-error`);
        const successElement = document.getElementById(`${prefix}-success`);
        const preview = document.getElementById(`${prefix}-preview`);
        const previewContent = document.getElementById('split-preview-content');
        const downloadBtn = document.getElementById('split-download');
        const splitColumn = document.getElementById('split-column').value;

        if (fileInput.files.length === 0) { showError(errorElement, '请先上传文件'); return; }
        if (!splitColumn) { showError(errorElement, '请选择拆分列'); return; }

        preview.style.display = 'none';
        errorElement.style.display = 'none';
        successElement.style.display = 'none';
        loader.style.display = 'block';
        progress.style.width = '0%';
        logEvent(`开始按列拆分: ${splitColumn}`);

        try {
            const formData = new FormData();
            formData.append('file', fileInput.files[0]);
            formData.append('split_column', splitColumn);
            let progressInterval = simulateProgress(progress, 2000);

            const splitResponse = await fetch(`${API_BASE_URL}/api/split`, { method: 'POST', body: formData });
            clearInterval(progressInterval);
            progress.style.width = '100%';

            if (!splitResponse.ok) {
                const errorData = await splitResponse.json().catch(() => ({}));
                throw new Error(errorData.detail || `拆分请求失败 (${splitResponse.status})`);
            }

            const blob = await splitResponse.blob();
            logEvent('拆分完成，ZIP文件已生成');
            previewContent.innerHTML = `<p style="padding: 20px;">文件已根据 <strong>${escapeHtml(splitColumn)}</strong> 列拆分完成，点击下方按钮即可下载包含所有文件的ZIP压缩包。</p>`;
            const url = window.URL.createObjectURL(blob);
            downloadBtn.onclick = function(event) {
                event.preventDefault();
                logEvent('用户点击下载拆分文件按钮');
                const tempLink = document.createElement('a');
                tempLink.href = url;
                tempLink.download = 'split_files.zip';
                document.body.appendChild(tempLink);
                tempLink.click();
                document.body.removeChild(tempLink);
                // 不立即 revokeObjectURL, 允许用户重复点击下载
            };

            loader.style.display = 'none';
            successElement.textContent = `拆分完成！请点下方按钮下载 ZIP 文件。`;
            successElement.style.display = 'block';
            preview.style.display = 'block';
        } catch (error) {
            loader.style.display = 'none';
            showError(errorElement, error.message);
            logEvent('拆分失败: ' + error.message);
        }
    });

    // 清理功能提交 (已集成真实API调用)
    document.getElementById('clean-button').addEventListener('click', async (e) => {
        e.preventDefault();
        const prefix = 'clean';
        const fileInput = document.getElementById(`${prefix}-file-input`);
        const loader = document.getElementById(`${prefix}-loader`);
        const progress = document.getElementById(`${prefix}-progress`);
        const errorElement = document.getElementById(`${prefix}-error`);
        const successElement = document.getElementById(`${prefix}-success`);
        const preview = document.getElementById(`${prefix}-preview`);
        const statsContainer = document.getElementById('clean-stats');
        const previewContent = document.getElementById('clean-preview-content');
        const downloadBtn = document.getElementById('clean-download');

        const removeEmptyRows = document.querySelector('input[name="clean_options"][value="remove_empty_rows"]').checked;
        const removeEmptyCols = document.querySelector('input[name="clean_options"][value="remove_empty_cols"]').checked;
        const trimSpaces = document.querySelector('input[name="clean_options"][value="trim_spaces"]').checked;

        if (fileInput.files.length === 0) { showError(errorElement, '请先上传文件'); return; }

        preview.style.display = 'none';
        errorElement.style.display = 'none';
        successElement.style.display = 'none';
        loader.style.display = 'block';
        progress.style.width = '0%';
        logEvent('开始清理表格...');

        try {
            const formData = new FormData();
            formData.append('file', fileInput.files[0]);
            formData.append('remove_empty_rows', removeEmptyRows);
            formData.append('remove_empty_cols', removeEmptyCols);
            formData.append('trim_spaces', trimSpaces);

            let progressInterval = simulateProgress(progress, 1500);
            const previewResponse = await fetch(`${API_BASE_URL}/api/clean/preview`, { method: 'POST', body: formData });
            clearInterval(progressInterval);
            progress.style.width = '100%';

            if (!previewResponse.ok) {
                const errorData = await previewResponse.json().catch(() => ({}));
                throw new Error(errorData.detail || `预览请求失败 (${previewResponse.status})`);
            }

            const previewData = await previewResponse.json();
            logEvent('清理预览数据获取成功');

            // 动态生成统计信息
            statsContainer.innerHTML = `
                <div class="stat-item"><div>原始行数</div><div class="stat-value">${previewData.original_rows}</div></div>
                <div class="stat-item"><div>清理后行数</div><div class="stat-value">${previewData.cleaned_rows}</div></div>
                <div class="stat-item"><div>原始列数</div><div class="stat-value">${previewData.original_cols}</div></div>
                <div class="stat-item"><div>清理后列数</div><div class="stat-value">${previewData.cleaned_cols}</div></div>
            `;

            let tableHTML = '';
            if (previewData.preview_data && previewData.preview_data.length > 0 && previewData.preview_columns) {
                tableHTML = '<table><thead><tr>';
                previewData.preview_columns.forEach(col => { tableHTML += `<th>${escapeHtml(col)}</th>`; });
                tableHTML += '</tr></thead><tbody>';
                previewData.preview_data.forEach(row => {
                    tableHTML += '<tr>';
                    previewData.preview_columns.forEach(col => {
                        const cellValue = row[col] != null ? row[col] : "";
                        tableHTML += `<td>${escapeHtml(String(cellValue))}</td>`;
                    });
                    tableHTML += '</tr>';
                });
                tableHTML += '</tbody></table>';
            } else {
                 tableHTML = '<p>清理后数据为空或无法生成预览。</p>';
            }
            previewContent.innerHTML = tableHTML;

            loader.style.display = 'none';
            const rowsRemoved = previewData.original_rows - previewData.cleaned_rows;
            const colsRemoved = previewData.original_cols - previewData.cleaned_cols;
            successElement.textContent = `清理完成！移除了 ${rowsRemoved} 行和 ${colsRemoved} 列。`;
            successElement.style.display = 'block';
            preview.style.display = 'block';

            downloadBtn.onclick = async function(event) {
                event.preventDefault();
                logEvent('用户点击下载清理文件按钮');
                loader.style.display = 'block';
                progress.style.width = '0%';
                errorElement.style.display = 'none';
                successElement.style.display = 'none';
                let downloadProgressInterval = simulateProgress(progress, 2000);

                try {
                    const downloadResponse = await fetch(`${API_BASE_URL}/api/clean`, { method: 'POST', body: formData });
                    clearInterval(downloadProgressInterval);
                    progress.style.width = '100%';

                    if (!downloadResponse.ok) {
                        const errorData = await downloadResponse.json().catch(() => ({}));
                        throw new Error(errorData.detail || `下载请求失败 (${downloadResponse.status})`);
                    }

                    const blob = await downloadResponse.blob();
                    const url = window.URL.createObjectURL(blob);
                    const tempLink = document.createElement('a');
                    tempLink.href = url;
                    tempLink.download = 'cleaned_data.xlsx';
                    document.body.appendChild(tempLink);
                    tempLink.click();
                    document.body.removeChild(tempLink);
                    window.URL.revokeObjectURL(url);

                    loader.style.display = 'none';
                    successElement.textContent = '清理后的文件下载成功！';
                    successElement.style.display = 'block';
                    logEvent('清理文件下载成功');
                } catch (downloadError) {
                     loader.style.display = 'none';
                     showError(errorElement, `下载失败: ${downloadError.message}`);
                     logEvent('下载失败: ' + downloadError.message);
                }
            };
        } catch (error) {
            loader.style.display = 'none';
            showError(errorElement, error.message);
            logEvent('清理失败: ' + error.message);
        }
    });

    // --- "不卷文档" (PDF to Image) 模块逻辑 ---
    
    // 文件处理逻辑已经存在于 handleFiles 函数中，这里直接复用
    // 只需确保 HTML 中的 ID 正确即可 (`pdf2img-file-input`, `pdf2img-file-list`, etc.)

    // "开始转换" 按钮的点击事件
    document.getElementById('pdf2img-button').addEventListener('click', async (e) => {
        e.preventDefault();
        const prefix = 'pdf2img';
        const fileInput = document.getElementById(`${prefix}-file-input`);
        const loader = document.getElementById(`${prefix}-loader`);
        const errorElement = document.getElementById(`${prefix}-error`);
        const successElement = document.getElementById(`${prefix}-success`);
        const preview = document.getElementById(`${prefix}-preview`);
        const previewContent = document.getElementById('pdf2img-preview-content');
        const downloadBtn = document.getElementById('pdf2img-download');

        // 获取转换选项
        const imageFormat = document.querySelector('input[name="image_format"]:checked').value;
        const imageDpi = document.getElementById('image-dpi').value;

        if (fileInput.files.length === 0) { 
            showError(errorElement, '请先上传一个 PDF 文件'); 
            return; 
        }

        // 重置UI状态
        preview.style.display = 'none';
        errorElement.style.display = 'none';
        successElement.style.display = 'none';
        loader.style.display = 'block';
        logEvent(`开始PDF转换... 格式: ${imageFormat}, DPI: ${imageDpi}`);

        // 创建 FormData 用于API请求
        const formData = new FormData();
        formData.append('file', fileInput.files[0]);
        formData.append('format', imageFormat);
        formData.append('dpi', imageDpi);

        try {
            const response = await fetch(`${API_BASE_URL}/api/pdf-to-images`, {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `转换失败 (${response.status})`);
            }

            // 成功后，后端应返回zip文件的二进制数据
            const blob = await response.blob();
            logEvent('PDF 转换成功，已收到 ZIP 文件');

            // 隐藏加载器，显示成功信息和预览区
            loader.style.display = 'none';
            successElement.textContent = `转换成功！您的 PDF 已被转换为图片并打包。`;
            successElement.style.display = 'block';
            
            // 在预览区显示一些有用的信息
            previewContent.innerHTML = `<p style="padding: 20px;">文件 <strong>${escapeHtml(fileInput.files[0].name)}</strong> 已成功处理。请点击下方按钮下载包含所有图片的 ZIP 压缩包。</p>`;
            preview.style.display = 'block';

            // 设置下载按钮
            const url = window.URL.createObjectURL(blob);
            downloadBtn.href = url;
            // 动态设置下载文件名
            const originalFilename = fileInput.files[0].name.replace(/\.pdf$/i, '');
            downloadBtn.download = `${originalFilename}_images.zip`;

        } catch (error) {
            loader.style.display = 'none';
            showError(errorElement, error.message);
            logEvent('PDF 转换失败: ' + error.message);
        }
    });

    // --- PDF 合并功能 ---
    const pdfmergePrefix = 'pdfmerge';
    const pdfmergeFileInput = document.getElementById(`${pdfmergePrefix}-file-input`);
    const pdfmergePreviewBox = document.getElementById(`${pdfmergePrefix}-preview`);
    const pdfmergePreviewContent = document.getElementById(`${pdfmergePrefix}-preview-content`);
    const pdfmergeButton = document.getElementById(`${pdfmergePrefix}-button`);
    const pdfmergeLoader = document.getElementById(`${pdfmergePrefix}-loader`);
    const pdfmergeProgress = document.getElementById(`${pdfmergePrefix}-progress`);
    const pdfmergeError = document.getElementById(`${pdfmergePrefix}-error`);
    const pdfmergeSuccess = document.getElementById(`${pdfmergePrefix}-success`);
    const pdfmergeTotalPages = document.getElementById(`${pdfmergePrefix}-total-pages`);
    const pdfmergeTotalSize = document.getElementById(`${pdfmergePrefix}-total-size`);
    const pdfmergeDownload = document.getElementById(`${pdfmergePrefix}-download`);

    let pdfmergeLastFormData = null; // 保存预览用的 FormData，下载时复用

    // 点击合并（预览）
    pdfmergeButton.addEventListener('click', async (e) => {
        e.preventDefault();
        if (pdfmergeFileInput.files.length === 0) {
            showError(pdfmergeError, '请先上传 PDF 文件');
            return;
        }

        // UI 重置
        pdfmergePreviewBox.style.display = 'none';
        pdfmergeError.style.display = 'none';
        pdfmergeSuccess.style.display = 'none';
        pdfmergeLoader.style.display = 'block';
        pdfmergeProgress.style.width = '0%';

        // 构建 FormData
        const formData = new FormData();
        for (let i = 0; i < pdfmergeFileInput.files.length; i++) {
            formData.append('files', pdfmergeFileInput.files[i]);
        }
        document.querySelectorAll('#pdfmerge .options-card input[type="checkbox"]:checked')
            .forEach(opt => formData.append('merge_options', opt.value));

        pdfmergeLastFormData = formData; // 保存，后面下载时复用

        try {
            logEvent('开始 PDF 合并预览请求...');
            let progressInterval = simulateProgress(pdfmergeProgress, 1500);

            const res = await fetch(`${API_BASE_URL}/api/pdfmerge/preview`, {
                method: 'POST',
                body: formData
            });

            clearInterval(progressInterval);
            pdfmergeProgress.style.width = '100%';

            if (!res.ok) {
                const errData = await res.json().catch(() => ({}));
                throw new Error(errData.detail || `预览请求失败 (${res.status})`);
            }

            const data = await res.json();
            pdfmergeLoader.style.display = 'none';
            pdfmergeSuccess.textContent = '预览完成，请点击下载按钮获取 PDF';
            pdfmergeSuccess.style.display = 'block';

            // 假设后端返回字段：total_pages, total_size, actions
            pdfmergeTotalPages.textContent = data.total_pages ?? '-';
            pdfmergeTotalSize.textContent = formatFileSize(data.total_size ?? 0);

            pdfmergePreviewBox.style.display = 'block';
            pdfmergeDownload.style.display = 'inline-block'; // 确保下载按钮可见

        } catch (err) {
            pdfmergeLoader.style.display = 'none';
            showError(pdfmergeError, err.message);
            logEvent('PDF 合并预览失败: ' + err.message);
        }
    });

    // 点击下载 PDF
    pdfmergeDownload.addEventListener('click', async (e) => {
        e.preventDefault();
        if (!pdfmergeLastFormData) {
            showError(pdfmergeError, '请先进行预览');
            return;
        }

        try {
            logEvent('开始 PDF 下载请求...');
            const res = await fetch(`${API_BASE_URL}/api/pdfmerge`, {
                method: 'POST',
                body: pdfmergeLastFormData
            });

            if (!res.ok) {
                throw new Error(`下载失败 (${res.status})`);
            }

            const blob = await res.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'merged.pdf';
            document.body.appendChild(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(url);

            logEvent('PDF 下载完成');
        } catch (err) {
            showError(pdfmergeError, err.message);
        }
    });


    // --- 主导航切换逻辑 ---
    const mainNavLinks = document.querySelectorAll('.main-nav li');
    const pageSections = document.querySelectorAll('.page-section');

    mainNavLinks.forEach(link => {
        link.addEventListener('click', function(e) {
        // 总是阻止默认行为
        e.preventDefault();
        
        // 获取<li>内的<a>标签
        const anchor = this.querySelector('a');
        if (!anchor) return;
        
        // 更新导航active状态
        mainNavLinks.forEach(item => item.classList.remove('active'));
        this.classList.add('active');

        // 获取目标ID并切换板块
        const targetId = anchor.getAttribute('href');
        const targetSection = document.querySelector(targetId);
        
        if (targetSection) {
            pageSections.forEach(section => section.classList.remove('active'));
            targetSection.classList.add('active');
        }
        });
    });

    // 确保 uploadAreas 能找到所有 .file-upload-wrapper
    console.log('上传区域数量:', uploadAreas.length);
});

