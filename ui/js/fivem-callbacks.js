// Callbacks para integración con FiveM
const FiveMCallbacks = {
    // Verificar si estamos en el entorno de FiveM
    isFiveM: typeof GetParentResourceName !== 'undefined',
    
    // Lista de callbacks permitidos
    allowedCallbacks: [
        'advance-manager:getPlayerBusiness',
        'advance-manager:depositFunds',
        'advance-manager:withdrawFunds',
        'advance-manager:hireEmployee',
        'advance-manager:fireEmployee',
        'advance-manager:getBusinessEmployees',
        'advance-manager:updateEmployeeWage',
        'advance-manager:updateEmployeeGrade',
        'advance-manager:getNearestPlayer',
        'advance-manager:getBusinessFunds',
        'closeUI'
    ],
    
    // Inicializar callbacks
    init() {
        if (this.isFiveM) {
            this.setupFiveMCallbacks();
        } else {
            console.log('Running in browser mode - using mock data');
        }
    },
    
    // Configurar callbacks reales para FiveM
    setupFiveMCallbacks() {
        // Sobrescribir BusinessAPI con callbacks reales
        Object.assign(BusinessAPI, {
            // Obtener información del negocio
            async getBusinessInfo() {
                return new Promise((resolve, reject) => {
                    this.performCallback('advance-manager:getPlayerBusiness', {}, (result) => {
                        if (result) {
                            const previousBusiness = BusinessAPI.currentBusiness || {};
                            BusinessAPI.currentBusiness = {
                                ...previousBusiness,
                                ...result,
                                jobName: result.job_name || result.jobName || result.job || result.jobLabel || previousBusiness.jobName
                            };

                            if (!Array.isArray(BusinessAPI.currentBusiness.employees)) {
                                BusinessAPI.currentBusiness.employees = [];
                            }

                            if (typeof BusinessManager !== 'undefined' && typeof BusinessManager.setSyncedEmployees === 'function') {
                                BusinessManager.setSyncedEmployees(BusinessAPI.currentBusiness.employees);
                            }

                            if (typeof BusinessManager !== 'undefined' && typeof BusinessManager.updateEmployeeCount === 'function') {
                                const countFromServer = typeof result.employee_count === 'number' ? result.employee_count : undefined;
                                BusinessManager.updateEmployeeCount(countFromServer);
                            }

                            resolve(BusinessAPI.currentBusiness);
                        } else {
                            reject({ error: 'No business found' });
                        }
                    });
                });
            },
            
            // Depositar fondos
            async depositFunds(amount) {
                return new Promise((resolve, reject) => {
                    this.performCallback('advance-manager:depositFunds', { amount }, (success, message) => {
                        if (success) {
                            resolve({ success: true, message: message });
                        } else {
                            reject({ error: message });
                        }
                    });
                });
            },
            
            // Retirar fondos
            async withdrawFunds(amount) {
                return new Promise((resolve, reject) => {
                    this.performCallback('advance-manager:withdrawFunds', { amount }, (success, message) => {
                        if (success) {
                            resolve({ success: true, message: message });
                        } else {
                            reject({ error: message });
                        }
                    });
                });
            },
            
            // Contratar empleado
            async hireEmployee(playerId, grade) {
                return new Promise((resolve, reject) => {
                    this.performCallback('advance-manager:hireEmployee', { 
                        playerId, 
                        grade
                    }, (success, message) => {
                        if (success) {
                            resolve({ success: true, message: message });
                        } else {
                            reject({ error: message });
                        }
                    });
                });
            },
            
            // Despedir empleado
            async fireEmployee(employeeId) {
                return new Promise((resolve, reject) => {
                    this.performCallback('advance-manager:fireEmployee', { 
                        employeeId 
                    }, (success, message) => {
                        if (success) {
                            resolve({ success: true, message: message });
                        } else {
                            reject({ error: message });
                        }
                    });
                });
            },
            
            // Obtener empleados
            async getEmployees() {
                return new Promise((resolve, reject) => {
                    this.performCallback('advance-manager:getBusinessEmployees', {}, (employees) => {
                        if (employees) {
                            BusinessAPI.currentBusiness = BusinessAPI.currentBusiness || {};
                            BusinessAPI.currentBusiness.employees = Array.isArray(employees) ? employees : [];

                            if (typeof BusinessManager !== 'undefined' && typeof BusinessManager.setSyncedEmployees === 'function') {
                                BusinessManager.setSyncedEmployees(BusinessAPI.currentBusiness.employees);
                            }

                            if (typeof BusinessManager !== 'undefined' && typeof BusinessManager.updateEmployeeCount === 'function') {
                                BusinessManager.updateEmployeeCount(BusinessAPI.currentBusiness.employees.length);
                            }

                            resolve(BusinessAPI.currentBusiness.employees);
                        } else {
                            reject({ error: 'Failed to load employees' });
                        }
                    });
                });
            },
            
            // Actualizar salario de empleado
            async updateEmployeeWage(employeeId, newWage) {
                return new Promise((resolve, reject) => {
                    this.performCallback('advance-manager:updateEmployeeWage', { 
                        employeeId, 
                        newWage 
                    }, (success, message) => {
                        if (success) {
                            resolve({ success: true, message: message });
                        } else {
                            reject({ error: message });
                        }
                    });
                });
            },
            
            // Actualizar grado de empleado
            async updateEmployeeGrade(employeeId, newGrade) {
                return new Promise((resolve, reject) => {
                    this.performCallback('advance-manager:updateEmployeeGrade', { 
                        employeeId, 
                        newGrade 
                    }, (success, message) => {
                        if (success) {
                            resolve({ success: true, message: message });
                        } else {
                            reject({ error: message });
                        }
                    });
                });
            },
            
            // Obtener jugador más cercano
            async getNearestPlayer() {
                return new Promise((resolve, reject) => {
                    this.performCallback('advance-manager:getNearestPlayer', {}, (playerId) => {
                        if (playerId) {
                            resolve(playerId);
                        } else {
                            reject({ error: 'No players found nearby' });
                        }
                    });
                });
            },
            
            // Obtener fondos del negocio
            async getBusinessFunds() {
                return new Promise((resolve, reject) => {
                    this.performCallback('advance-manager:getBusinessFunds', {}, (funds) => {
                        if (funds !== false) {
                            resolve(funds);
                        } else {
                            reject({ error: 'Failed to get business funds' });
                        }
                    });
                });
            }
        });
        
        // Sobrescribir funciones de BusinessManager para FiveM
        Object.assign(BusinessManager, {
            // Función para obtener jugador más cercano
            async getNearestPlayer() {
                if (!FiveMCallbacks.isFiveM) {
                    // Fallback para navegador
                    this.showLoading('Finding nearest player...');
                    
                    setTimeout(() => {
                        this.hideLoading();
                        const nearestPlayerId = Math.floor(Math.random() * 100) + 1;
                        $('#playerId').val(nearestPlayerId);
                        this.showToast(`Found nearest player: ID ${nearestPlayerId}`, 'success');
                    }, 1500);
                    return;
                }
                
                try {
                    this.showLoading('Finding nearest player...');
                    const playerId = await BusinessAPI.getNearestPlayer();
                    this.hideLoading();
                    
                    $('#playerId').val(playerId);
                    this.showToast(`Found nearest player: ID ${playerId}`, 'success');
                } catch (error) {
                    this.hideLoading();
                    this.showToast(error.error || 'No players found nearby', 'error');
                }
            },
            
            // Cargar datos reales del negocio
            async loadBusinessData() {
                if (!FiveMCallbacks.isFiveM) {
                    this.loadMockData();
                    return;
                }
                
                try {
                    const businessInfo = await BusinessAPI.getBusinessInfo();
                    
                    if (businessInfo) {
                        // Actualizar UI con datos reales
                        $('#jobTitle span').text(businessInfo.job_name || 'Unknown Job');
                        $('#businessName').text(businessInfo.name || 'Unknown Business');
                        $('#businessFunds').text(`$${businessInfo.funds?.toLocaleString() || '0'}`);
                        
                        // Obtener empleados y actualizar contador
                        const employees = await BusinessAPI.getEmployees();
                        $('#totalEmployees').text(employees?.length || '0');
                        
                        // Determinar rol del usuario
                        const userRole = $('#userRole');
                        if (businessInfo.is_boss) {
                            userRole.find('.role-badge').addClass('boss').text('BOSS');
                        } else {
                            userRole.find('.role-badge').addClass('employee').text('EMPLOYEE');
                        }
                        
                        // Actualizar nombre del usuario si está disponible
                        if (businessInfo.user_name) {
                            userRole.find('.user-name').text(businessInfo.user_name);
                        }
                    }
                } catch (error) {
                    console.error('Failed to load business data:', error);
                    this.showToast('Failed to load business data', 'error');
                }
            },
            
            // Sobrescribir showPanel para cargar datos reales
            showPanel() {
                this.isOpen = true;
                $('#overlay').addClass('active');
                $('#businessPanel').addClass('active');
                
                // Cargar datos reales o mock según el entorno
                this.loadBusinessData();
            },
            
            // Sobrescribir hidePanel para cerrar UI en FiveM
            hidePanel() {
                this.isOpen = false;
                $('#overlay').removeClass('active');
                $('#businessPanel').removeClass('active');
                
                // Cerrar NUI focus si estamos en FiveM
                if (FiveMCallbacks.isFiveM) {
                    $.post(`https://${GetParentResourceName()}/closeUI`, JSON.stringify({}));
                }
            }
        });
    },
    
    // Validar callback permitido
    validateCallback(callbackName) {
        return this.allowedCallbacks.includes(callbackName);
    },
    
    // Validar datos de entrada
    validateInput(data) {
        if (typeof data !== 'object' || data === null) {
            return false;
        }
        
        // Validar campos numéricos
        if (data.amount && (!Number.isInteger(data.amount) || data.amount <= 0)) {
            return false;
        }
        
        if (data.playerId && (!Number.isInteger(data.playerId) || data.playerId <= 0)) {
            return false;
        }
        
        if (data.grade !== undefined && (!Number.isInteger(data.grade) || data.grade < 0 || data.grade > 4)) {
            return false;
        }
        
        // wage ya no es validado aquí, se asigna automáticamente desde QBCore shared
        
        if (data.employeeId && (!Number.isInteger(data.employeeId) || data.employeeId <= 0)) {
            return false;
        }
        
        return true;
    },
    
    // Función auxiliar para realizar callbacks
    performCallback(callbackName, data, callback) {
        // Validar callback
        if (!this.validateCallback(callbackName)) {
            console.error(`Security Alert: Unauthorized callback: ${callbackName}`);
            if (callback) callback(false, 'Unauthorized callback');
            return;
        }
        
        // Validar datos
        if (!this.validateInput(data)) {
            console.error(`Security Alert: Invalid data for callback: ${callbackName}`);
            if (callback) callback(false, 'Invalid data');
            return;
        }
        
        if (this.isFiveM) {
            // Verificar que estamos en el recurso correcto
            const resourceName = GetParentResourceName();
            if (resourceName !== 'advance-manager') {
                console.error(`Security Alert: Invalid resource name: ${resourceName}`);
                if (callback) callback(false, 'Invalid resource');
                return;
            }
            
            // Usar POST para comunicar con FiveM endpoints
            $.post(`https://${resourceName}/${callbackName}`, JSON.stringify(data), callback);
        } else {
            // Modo navegador - usar datos mock
            console.log(`Mock callback: ${callbackName}`, data);
            callback(true, 'Mock response');
        }
    },
    
    // Función para mostrar/ocultar panel desde FiveM
    togglePanel() {
        if (BusinessManager.isOpen) {
            BusinessManager.hidePanel();
        } else {
            BusinessManager.showPanel();
        }
    },
    
    // Función para cerrar panel desde FiveM
    closePanel() {
        BusinessManager.hidePanel();
    },
    
    // Función para mostrar notificación desde FiveM
    showNotification(message, type = 'info') {
        BusinessManager.showToast(message, type);
    },
    
    // Función para actualizar datos del negocio desde FiveM
    updateBusinessInfo(businessInfo) {
        if (businessInfo.funds !== undefined) {
            $('#businessFunds').text(`$${businessInfo.funds.toLocaleString()}`);
        }
        
        if (businessInfo.employeeCount !== undefined) {
            $('#totalEmployees').text(businessInfo.employeeCount);
        }
        
        if (businessInfo.name !== undefined) {
            $('#businessName').text(businessInfo.name);
        }
    }
};

// Función global para usar desde FiveM
window.FiveMCallbacks = FiveMCallbacks;

// Inicializar callbacks cuando el DOM esté listo
$(document).ready(function() {
    FiveMCallbacks.init();
});

// Funciones globales protegidas para FiveM
window.toggleBusinessPanel = () => {
    if (FiveMCallbacks.isFiveM) {
        FiveMCallbacks.togglePanel();
    } else {
        console.warn('Function only available in FiveM environment');
    }
};

window.closeBusinessPanel = () => {
    if (FiveMCallbacks.isFiveM) {
        FiveMCallbacks.closePanel();
    } else {
        console.warn('Function only available in FiveM environment');
    }
};

window.showBusinessNotification = (message, type) => {
    if (FiveMCallbacks.isFiveM && typeof message === 'string') {
        FiveMCallbacks.showNotification(message, type);
    } else {
        console.warn('Function only available in FiveM environment or invalid message');
    }
};

window.updateBusinessInfo = (info) => {
    if (FiveMCallbacks.isFiveM && typeof info === 'object') {
        FiveMCallbacks.updateBusinessInfo(info);
    } else {
        console.warn('Function only available in FiveM environment or invalid info');
    }
};
