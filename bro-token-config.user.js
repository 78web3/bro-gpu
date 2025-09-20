// ==UserScript==
// @name         $Bro Configuration
// @namespace    http://tampermonkey.net/
// @version      1.0
// @description  为 Bro Token 网站添加配置输入框
// @author       DarrenLuo
// @match        https://bro.charms.dev/*
// @run-at       document-start
// @grant        GM_xmlhttpRequest
// @grant        unsafeWindow
// @connect      *
// ==/UserScript==

(function() {
    'use strict';

    console.log('🚀 Bro Token 配置脚本开始加载...');

    // 创建配置面板
    function createConfigPanel() {
        // 检查是否已存在面板
        if (document.getElementById('bro-config-panel')) {
            return;
        }

        // 创建主面板
        const configPanel = document.createElement('div');
        configPanel.id = 'bro-config-panel';
        configPanel.style.cssText = `
            position: fixed;
            top: 80px;
            right: 20px;
            width: 380px;
            background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%);
            border: 1px solid #444;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
            z-index: 10000;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            color: #fff;
            backdrop-filter: blur(10px);
            display: block;
        `;

        // 标题
        const title = document.createElement('h3');
        title.textContent = 'Bro Token 配置';
        title.style.cssText = `
            margin: 0 0 20px 0;
            color: #ff6b35;
            font-size: 18px;
            font-weight: 600;
            text-align: center;
            border-bottom: 2px solid #ff6b35;
            padding-bottom: 10px;
        `;

        // 输入框容器
        const inputsContainer = document.createElement('div');
        inputsContainer.style.cssText = `
            display: flex;
            flex-direction: column;
            gap: 15px;
        `;

        // Prover 地址输入框
        const proverGroup = createInputGroupWithNote(
            'Prover 地址',
            'prover-address',
            'https://v7.charms.dev/spells/prove',
            '配置Prover接口地址，用于处理相关请求'
        );

        // 按钮容器
        const buttonContainer = document.createElement('div');
        buttonContainer.style.cssText = `
            display: flex;
            gap: 10px;
            margin-top: 20px;
            flex-wrap: wrap;
        `;

        // 保存按钮
        const saveBtn = document.createElement('button');
        saveBtn.textContent = '保存配置';
        saveBtn.style.cssText = `
            flex: 1;
            padding: 12px 20px;
            background: linear-gradient(135deg, #ff6b35 0%, #f7931e 100%);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            min-width: 100px;
        `;

        // 刷新按钮
        const refreshBtn = document.createElement('button');
        refreshBtn.textContent = '刷新页面';
        refreshBtn.style.cssText = `
            flex: 1;
            padding: 12px 20px;
            background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            min-width: 100px;
        `;


        // 按钮悬停效果
        [saveBtn, refreshBtn].forEach(btn => {
            btn.addEventListener('mouseenter', () => {
                btn.style.transform = 'translateY(-2px)';
                btn.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.3)';
            });
            btn.addEventListener('mouseleave', () => {
                btn.style.transform = 'translateY(0)';
                btn.style.boxShadow = 'none';
            });
        });

        // 组装面板
        inputsContainer.appendChild(proverGroup);
        buttonContainer.appendChild(saveBtn);
        buttonContainer.appendChild(refreshBtn);

        configPanel.appendChild(title);
        configPanel.appendChild(inputsContainer);
        configPanel.appendChild(buttonContainer);

        // 事件监听
        saveBtn.addEventListener('click', saveConfiguration);
        refreshBtn.addEventListener('click', () => window.location.reload());

        // 添加到页面
        document.body.appendChild(configPanel);

        // 加载已保存的配置
        loadConfiguration();
    }

    // 创建输入组
    function createInputGroup(label, id, placeholder) {
        const group = document.createElement('div');
        group.style.cssText = `
            display: flex;
            flex-direction: column;
            gap: 8px;
        `;

        const labelElement = document.createElement('label');
        labelElement.textContent = label;
        labelElement.style.cssText = `
            font-size: 14px;
            font-weight: 500;
            color: #ccc;
        `;

        const input = document.createElement('input');
        input.type = 'text';
        input.id = id;
        input.placeholder = placeholder;
        input.style.cssText = `
            padding: 12px;
            border: 1px solid #444;
            border-radius: 8px;
            background: rgba(255, 255, 255, 0.1);
            color: #fff;
            font-size: 14px;
            transition: all 0.3s ease;
        `;

        input.addEventListener('focus', () => {
            input.style.borderColor = '#ff6b35';
            input.style.background = 'rgba(255, 255, 255, 0.15)';
        });

        input.addEventListener('blur', () => {
            input.style.borderColor = '#444';
            input.style.background = 'rgba(255, 255, 255, 0.1)';
        });

        group.appendChild(labelElement);
        group.appendChild(input);

        return group;
    }

    // 创建带说明的输入组
    function createInputGroupWithNote(label, id, placeholder, note) {
        const group = document.createElement('div');
        group.style.cssText = `
            display: flex;
            flex-direction: column;
            gap: 5px;
        `;

        const labelElement = document.createElement('label');
        labelElement.textContent = label;
        labelElement.style.cssText = `
            font-size: 12px;
            font-weight: 500;
            color: #ccc;
        `;

        const input = document.createElement('input');
        input.type = 'text';
        input.id = id;
        input.placeholder = placeholder;
        input.style.cssText = `
            padding: 10px;
            border: 1px solid #444;
            border-radius: 6px;
            background: rgba(255, 255, 255, 0.1);
            color: #fff;
            font-size: 14px;
            transition: all 0.3s ease;
        `;

        const noteElement = document.createElement('div');
        noteElement.textContent = note;
        noteElement.style.cssText = `
            font-size: 11px;
            color: #999;
            font-style: italic;
            line-height: 1.3;
            margin-top: 2px;
        `;

        input.addEventListener('focus', () => {
            input.style.borderColor = '#ff6b35';
            input.style.background = 'rgba(255, 255, 255, 0.15)';
        });

        input.addEventListener('blur', () => {
            input.style.borderColor = '#444';
            input.style.background = 'rgba(255, 255, 255, 0.1)';
        });

        group.appendChild(labelElement);
        group.appendChild(input);
        group.appendChild(noteElement);

        return group;
    }

    // 保存配置
    function saveConfiguration() {
        const proverAddress = document.getElementById('prover-address').value;

        const config = {
            proverAddress: proverAddress
        };

        localStorage.setItem('bro-token-config', JSON.stringify(config));

        // 显示保存成功提示
        showNotification('✅ 配置已保存！', 'success');
        
        // 保存后立即检测ready接口
        setTimeout(() => {
            testProverConnection();
        }, 500);
    }

    // 加载配置
    function loadConfiguration() {
        const savedConfig = localStorage.getItem('bro-token-config');
        if (savedConfig) {
            const config = JSON.parse(savedConfig);
            document.getElementById('prover-address').value = config.proverAddress || '';
        }
    }

    // 获取配置
    function getConfiguration() {
        const savedConfig = localStorage.getItem('bro-token-config');
        return savedConfig ? JSON.parse(savedConfig) : {
            proverAddress: 'https://v7.charms.dev/spells/prove'
        };
    }

    // 显示通知
    function showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.textContent = message;

        let backgroundColor;
        switch(type) {
            case 'success':
                backgroundColor = '#4CAF50';
                break;
            case 'error':
                backgroundColor = '#f44336';
                break;
            default:
                backgroundColor = '#2196F3';
        }

        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: ${backgroundColor};
            color: white;
            padding: 12px 20px;
            border-radius: 8px;
            z-index: 10003;
            font-size: 14px;
            font-weight: 500;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
            animation: slideIn 0.3s ease;
            max-width: 300px;
            margin-bottom: 10px;
        `;

        const style = document.createElement('style');
        style.textContent = `
            @keyframes slideIn {
                from { transform: translateX(100%); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
            }
        `;
        document.head.appendChild(style);

        document.body.appendChild(notification);

        setTimeout(() => {
            notification.remove();
            style.remove();
        }, 3000);
    }

    // 拦截并重定向prover请求
    function interceptProverRequests() {
        console.log('🚀 启动Prover请求拦截器...');
        
        const targetProverUrl = 'https://v7.charms.dev/spells/prove';
        console.log('🎯 目标拦截URL:', targetProverUrl);
        
        // 劫持 fetch 请求
        const originalFetch = unsafeWindow.fetch;
        unsafeWindow.fetch = async function(...args) {
            const url = args[0];
            
            console.log('🔍 Fetch请求:', url);

            // 检查是否是目标prover请求
            if (url === targetProverUrl) {
                console.log('🎯 拦截到Prover请求 (fetch):', url);
                
                const config = getConfiguration();
                const customProverUrl = config.proverAddress;
                console.log('🔄 重定向到:', customProverUrl);
                
                // 检查是否是默认配置，如果是则直接使用原始fetch
                if (customProverUrl === targetProverUrl) {
                    console.log('ℹ️ 使用默认配置，直接请求原地址');
                    return await originalFetch.apply(this, args);
                }
                
                // 使用GM_xmlhttpRequest重定向请求
                return new Promise((resolve, reject) => {
                    const method = (args[1] && args[1].method) || 'GET';
                    const headers = (args[1] && args[1].headers) || {};
                    
                    GM_xmlhttpRequest({
                        method: method,
                        url: customProverUrl,
                        headers: {
                            'User-Agent': navigator.userAgent,
                            'Accept': '*/*',
                            ...headers
                        },
                        data: args[1] && args[1].body,
                        onload: function(response) {
                            console.log('✅ GM_xmlhttpRequest请求成功，状态:', response.status);
                            
                            // 创建Response对象
                            const responseHeaders = new Headers();
                            Object.keys(response.responseHeaders || {}).forEach(key => {
                                responseHeaders.set(key, response.responseHeaders[key]);
                            });
                            
                            resolve(new Response(response.responseText || response.response, {
                                status: response.status,
                                statusText: response.statusText || 'OK',
                                headers: responseHeaders
                            }));
                        },
                        onerror: function(error) {
                            console.error('❌ GM_xmlhttpRequest请求失败:', error);
                            reject(new Error(`Request failed: ${error.error || 'Unknown error'}`));
                        },
                        ontimeout: function() {
                            console.error('❌ GM_xmlhttpRequest请求超时');
                            reject(new Error('Request timeout'));
                        }
                    });
                });
            }
            
            return await originalFetch.apply(this, args);
        };
        
        // 劫持 XMLHttpRequest
        const originalXHROpen = unsafeWindow.XMLHttpRequest.prototype.open;
        const originalXHRSend = unsafeWindow.XMLHttpRequest.prototype.send;
        
        unsafeWindow.XMLHttpRequest.prototype.open = function(method, url, ...args) {
            this._originalUrl = url;
            this._originalMethod = method;
            
            // 检查是否是目标prover请求
            if (url === targetProverUrl) {
                console.log('🎯 拦截到Prover请求 (XHR):', url);
                
                const config = getConfiguration();
                const customProverUrl = config.proverAddress;
                console.log('🔄 重定向到:', customProverUrl);
                
                // 对于XHR，我们只能重定向URL
                if (customProverUrl !== targetProverUrl) {
                    url = customProverUrl;
                }
            }
            
            return originalXHROpen.apply(this, [method, url, ...args]);
        };
        
        unsafeWindow.XMLHttpRequest.prototype.send = function(...args) {
            return originalXHRSend.apply(this, args);
        };
        
        console.log('🔧 Prover请求拦截器已启动');
    }

    // 页面加载完成后创建配置面板
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            createConfigPanel();
            interceptProverRequests();
        });
    } else {
        createConfigPanel();
        interceptProverRequests();
    }

    // 生成ready接口地址
    function generateReadyUrl(proverUrl) {
        try {
            const url = new URL(proverUrl);
            // 将路径替换为 /ready
            url.pathname = '/ready';
            return url.toString();
        } catch (e) {
            console.error('❌ URL解析失败:', e);
            return null;
        }
    }

    // 测试配置地址连接
    function testProverConnection() {
        const config = getConfiguration();
        const proverUrl = config.proverAddress;
        
        // 检查是否是默认配置
        if (proverUrl === 'https://v7.charms.dev/spells/prove') {
            console.log('ℹ️ 使用默认Prover地址，跳过ready检测');
            return;
        }
        
        console.log('🧪 检测Prover服务状态...');
        console.log('🎯 Prover地址:', proverUrl);
        
        // 生成对应的ready接口地址
        const readyUrl = generateReadyUrl(proverUrl);
        if (!readyUrl) {
            console.error('❌ 无法生成ready接口地址');
            showNotification('❌ Prover地址格式错误', 'error');
            return;
        }
        
        console.log('🔍 检测ready接口:', readyUrl);
        
        // 使用GM_xmlhttpRequest测试ready接口
        GM_xmlhttpRequest({
            method: 'GET',
            url: readyUrl,
            timeout: 10000,
            headers: {
                'User-Agent': navigator.userAgent,
                'Accept': '*/*'
            },
            onload: function(response) {
                if (response.status === 200) {
                    console.log('✅ Ready接口检测成功！');
                    console.log('📊 状态码:', response.status);
                    console.log('📄 响应内容:', response.responseText.substring(0, 200));
                    console.log('🌐 检测地址:', readyUrl);
                    
                    // 显示成功通知
                    showNotification(`✅ Prover服务正常 (${response.status})`, 'success');
                } else {
                    console.warn('⚠️ Ready接口返回非200状态码');
                    console.log('📊 状态码:', response.status);
                    console.log('📄 响应内容:', response.responseText.substring(0, 200));
                    
                    // 显示警告通知
                    showNotification(`⚠️ Prover服务异常 (${response.status})`, 'error');
                }
            },
            onerror: function(error) {
                console.error('❌ Ready接口检测失败:', error);
                
                // 显示失败通知
                showNotification('❌ Prover服务不可用，请检查配置', 'error');
            },
            ontimeout: function() {
                console.error('⏰ Ready接口检测超时');
                showNotification('⏰ Prover服务响应超时', 'error');
            }
        });
    }


    // 暴露配置函数到全局
    unsafeWindow.getBroConfig = getConfiguration;
    unsafeWindow.testProverConnection = testProverConnection;

    console.log('🔧 Bro Token 配置脚本已加载！');
    console.log('🔧 全局函数已暴露：');
    console.log('   - window.getBroConfig');
    console.log('   - window.testProverConnection');

    // 脚本加载完成后自动测试Prover连接
    setTimeout(() => {
        testProverConnection();
    }, 1000);

})();