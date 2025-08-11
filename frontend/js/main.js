// frontend/js/main.js

const fileInput = document.getElementById('file-input');
const fileList = document.getElementById('file-list');
const submitButton = document.getElementById('submit-button');
const form = document.getElementById('upload-form');
const loader = document.getElementById('loader');
const errorMessage = document.getElementById('error-message');

// 后端 API 的地址
const API_ENDPOINT = 'http://127.0.0.1:8000/api/merge';

fileInput.addEventListener('change', () => {
    fileList.innerHTML = '';
    if (fileInput.files.length > 0) {
        for (const file of fileInput.files) {
            const fileItem = document.createElement('div');
            fileItem.textContent = file.name;
            fileList.appendChild(fileItem);
        }
        submitButton.disabled = false;
    } else {
        submitButton.disabled = true;
    }
});

form.addEventListener('submit', async (event) => {
    event.preventDefault();// 1. 阻止表单的默认提交行为

    // 2. 显示加载状态，隐藏按钮和旧的错误信息
    submitButton.style.display = 'none';
    errorMessage.style.display = 'none';
    loader.style.display = 'block';

    const formData = new FormData(form); // 3. 收集表单数据 (包括文件和选项)

    try {
        // 4. 使用fetch API异步发送请求
        // **关键改动**: 使用绝对 URL 来调用后端 API
        const response = await fetch(API_ENDPOINT, {
            method: 'POST',
            body: formData,
        });

        // 5. 处理响应
        if (response.ok) {
            // 5a. 如果响应成功(200 OK)，则处理文件下载
            if (response.headers.get('Content-Type').includes('sheet')) {
                const blob = await response.blob(); // 获取文件内容的二进制对象
                const url = window.URL.createObjectURL(blob); // 创建一个临时的URL
                const a = document.createElement('a'); // 创建一个隐藏的下载链接
                a.style.display = 'none';
                a.href = url;
                a.download = 'merged_pro.xlsx'; // 设置下载文件名
                document.body.appendChild(a);
                a.click(); // 模拟点击以下载
                window.URL.revokeObjectURL(url); // 释放URL资源
                a.remove();
            }
        } else {
            // 5b. 如果服务器返回错误 (如 400, 500)
            const errorData = await response.json(); // FastAPI的HTTPException会返回JSON
            errorMessage.textContent = '错误: ' + (errorData.detail || '未知错误');
            errorMessage.style.display = 'block';
        }
    } catch (error) {
        // 6. 处理网络错误等
        errorMessage.textContent = '请求失败，请检查网络连接。';
        errorMessage.style.display = 'block';
    } finally {
        // 7. 无论成功或失败，最后都恢复UI到初始状态
        loader.style.display = 'none';
        submitButton.style.display = 'block';
        // 可选：清空文件选择，让用户可以开始下一次操作
        // fileInput.value = ''; 
        // fileList.innerHTML = '';
        // submitButton.disabled = true;
    }
});