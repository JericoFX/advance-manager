QBCore = exports['qb-core']:GetCoreObject()

local PlayerData = QBCore.Functions.GetPlayerData()
local currentBusiness = nil
local groupDigits = lib.math.groupdigits
local deepClone = lib.table.deepclone

-- Update player data on load
RegisterNetEvent('QBCore:Client:OnPlayerLoaded', function()
    PlayerData = QBCore.Functions.GetPlayerData()
end)

RegisterNetEvent('QBCore:Client:OnJobUpdate', function(JobInfo)
    PlayerData.job = JobInfo
end)

local function ensureOnFoot()
    local vehicle = lib.cache('vehicle')
    if vehicle and vehicle ~= false then
        lib.notify({
            title = 'Unavailable',
            description = 'Exit your vehicle before managing your business',
            type = 'error'
        })
        return false
    end

    return true
end

-- Create Business Interface (Admin only)
local function ShowCreateBusinessMenu()
    if not ensureOnFoot() then
        return
    end

    local availableJobs = lib.callback.await('advance-manager:getAvailableJobs', false)
    
    if not availableJobs then
        lib.notify({
            title = 'Error',
            description = 'Failed to load available jobs',
            type = 'error'
        })
        return
    end
    
    local jobOptions = {}
    for _, job in pairs(availableJobs) do
        table.insert(jobOptions, {
            value = job.name,
            label = job.label .. ' (' .. job.name .. ')'
        })
    end
    
    local input = lib.inputDialog('Create Business', {
        {type = 'input', label = 'Business Name', placeholder = 'Enter business name', required = true},
        {type = 'number', label = 'Owner ID', placeholder = 'Enter player ID', required = true},
        {type = 'select', label = 'Job Type', options = jobOptions, required = true},
        {type = 'number', label = 'Starting Funds', placeholder = 'Enter starting funds', default = 10000}
    })
    
    if input then
        TriggerServerEvent('advance-manager:createBusinessFromClient', input[1], input[2], input[3], input[4])
    end
end

-- Business Management Interface
local function ShowBusinessManagementMenu()
    if not ensureOnFoot() then
        return
    end

    local business = lib.callback.await('advance-manager:getPlayerBusiness', false)

    if not business then
        lib.notify({
            title = 'No Business',
            description = 'You do not own or work for any business',
            type = 'error'
        })
        return
    end

    currentBusiness = deepClone(business)

    local options = {
        {
            title = 'Business Information',
            description = ('Name: %s | Funds: $%s'):format(business.name, groupDigits(business.funds or 0)),
            icon = 'fas fa-info-circle',
            disabled = true
        },
        {
            title = 'Manage Employees',
            description = 'Hire, fire, and manage employees',
            icon = 'fas fa-users',
            onSelect = function()
                ShowEmployeeManagementMenu(business.id)
            end
        },
        {
            title = 'Financial Management',
            description = 'View and manage business finances',
            icon = 'fas fa-dollar-sign',
            onSelect = function()
                ShowFinancialManagementMenu(business.id)
            end
        }
    }
    
    lib.registerContext({
        id = 'business_management',
        title = 'Business Management',
        options = options
    })
    
    lib.showContext('business_management')
end

-- Employee Management Interface
local function ShowEmployeeManagementMenu(businessId)
    local employees = lib.callback.await('advance-manager:getBusinessEmployees', false, businessId)
    
    if not employees then
        lib.notify({
            title = 'Error',
            description = 'Failed to load employees or no permission',
            type = 'error'
        })
        return
    end
    
    local options = {
        {
            title = 'Hire Employee',
            description = 'Hire a new employee',
            icon = 'fas fa-user-plus',
            onSelect = function()
                ShowHireEmployeeMenu(businessId)
            end
        }
    }
    
    if #employees > 0 then
        table.insert(options, {
            title = 'Current Employees',
            description = 'Manage existing employees',
            icon = 'fas fa-users',
            disabled = true
        })
        
        for _, employee in pairs(employees) do
            table.insert(options, {
                title = employee.name,
                description = ('Grade: %s | Wage: $%s'):format(employee.grade, groupDigits(employee.wage or 0)),
                icon = 'fas fa-user',
                onSelect = function()
                    ShowEmployeeDetailsMenu(businessId, employee)
                end
            })
        end
    else
        table.insert(options, {
            title = 'No Employees',
            description = 'No employees currently hired',
            icon = 'fas fa-user-slash',
            disabled = true
        })
    end
    
    lib.registerContext({
        id = 'employee_management',
        title = 'Employee Management',
        options = options
    })
    
    lib.showContext('employee_management')
end

-- Hire Employee Interface
local function ShowHireEmployeeMenu(businessId)
    local input = lib.inputDialog('Hire Employee', {
        {type = 'number', label = 'Player ID', placeholder = 'Enter player ID to hire', required = true},
        {type = 'number', label = 'Grade', placeholder = 'Enter job grade (0-4)', required = true, min = 0, max = 4},
        {type = 'number', label = 'Wage', placeholder = 'Enter hourly wage', required = true, min = 10, max = 100}
    })
    
    if input then
        local success, message = lib.callback.await('advance-manager:hireEmployee', false, businessId, input[1], input[2], input[3])
        
        if success then
            lib.notify({
                title = 'Success',
                description = 'Employee hired successfully',
                type = 'success'
            })
            ShowEmployeeManagementMenu(businessId)
        else
            lib.notify({
                title = 'Error',
                description = message or 'Failed to hire employee',
                type = 'error'
            })
        end
    end
end

-- Employee Details Interface
local function ShowEmployeeDetailsMenu(businessId, employee)
    local options = {
        {
            title = 'Employee: ' .. employee.name,
            description = ('Grade: %s | Wage: $%s'):format(employee.grade, groupDigits(employee.wage or 0)),
            icon = 'fas fa-user',
            disabled = true
        },
        {
            title = 'Update Wage',
            description = 'Change employee wage',
            icon = 'fas fa-dollar-sign',
            onSelect = function()
                local input = lib.inputDialog('Update Wage', {
                    {type = 'number', label = 'New Wage', placeholder = 'Enter new wage', required = true, min = 10, max = 100, default = employee.wage}
                })
                
                if input then
                    local success = lib.callback.await('advance-manager:updateEmployeeWage', false, businessId, employee.citizenid, input[1])
                    
                    if success then
                        lib.notify({
                            title = 'Success',
                            description = 'Wage updated successfully',
                            type = 'success'
                        })
                        ShowEmployeeManagementMenu(businessId)
                    else
                        lib.notify({
                            title = 'Error',
                            description = 'Failed to update wage',
                            type = 'error'
                        })
                    end
                end
            end
        },
        {
            title = 'Update Grade',
            description = 'Change employee grade',
            icon = 'fas fa-arrow-up',
            onSelect = function()
                local input = lib.inputDialog('Update Grade', {
                    {type = 'number', label = 'New Grade', placeholder = 'Enter new grade (0-4)', required = true, min = 0, max = 4, default = employee.grade}
                })
                
                if input then
                    local success = lib.callback.await('advance-manager:updateEmployeeGrade', false, businessId, employee.citizenid, input[1])
                    
                    if success then
                        lib.notify({
                            title = 'Success',
                            description = 'Grade updated successfully',
                            type = 'success'
                        })
                        ShowEmployeeManagementMenu(businessId)
                    else
                        lib.notify({
                            title = 'Error',
                            description = 'Failed to update grade',
                            type = 'error'
                        })
                    end
                end
            end
        },
        {
            title = 'Fire Employee',
            description = 'Remove employee from business',
            icon = 'fas fa-user-times',
            onSelect = function()
                local confirm = lib.alertDialog({
                    header = 'Confirm Fire',
                    content = 'Are you sure you want to fire ' .. employee.name .. '?',
                    centered = true,
                    cancel = true
                })
                
                if confirm == 'confirm' then
                    local success = lib.callback.await('advance-manager:fireEmployee', false, businessId, employee.citizenid)
                    
                    if success then
                        lib.notify({
                            title = 'Success',
                            description = 'Employee fired successfully',
                            type = 'success'
                        })
                        ShowEmployeeManagementMenu(businessId)
                    else
                        lib.notify({
                            title = 'Error',
                            description = 'Failed to fire employee',
                            type = 'error'
                        })
                    end
                end
            end
        }
    }
    
    lib.registerContext({
        id = 'employee_details',
        title = 'Employee Details',
        options = options
    })
    
    lib.showContext('employee_details')
end

-- Financial Management Interface
local function ShowFinancialManagementMenu(businessId)
    -- Get current funds
    local currentFunds = lib.callback.await('advance-manager:getBusinessFunds', false, businessId) or 0

    local options = {
        {
            title = 'Current Funds',
            description = ('Business has $%s'):format(groupDigits(currentFunds)),
            icon = 'fas fa-wallet',
            disabled = true
        },
        {
            title = 'Deposit Funds',
            description = 'Add money to business account',
            icon = 'fas fa-plus',
            onSelect = function()
                local input = lib.inputDialog('Deposit Funds', {
                    {type = 'number', label = 'Amount', placeholder = 'Enter amount to deposit', required = true, min = 1}
                })
                
                if input then
                    local success, message = lib.callback.await('advance-manager:depositFunds', false, businessId, input[1])
                    
                    if success then
                        lib.notify({
                            title = 'Success',
                            description = message,
                            type = 'success'
                        })
                        ShowFinancialManagementMenu(businessId)
                    else
                        lib.notify({
                            title = 'Error',
                            description = message or 'Failed to deposit funds',
                            type = 'error'
                        })
                    end
                end
            end
        },
        {
            title = 'Withdraw Funds',
            description = 'Remove money from business account',
            icon = 'fas fa-minus',
            onSelect = function()
                local input = lib.inputDialog('Withdraw Funds', {
                    {type = 'number', label = 'Amount', placeholder = 'Enter amount to withdraw', required = true, min = 1}
                })
                
                if input then
                    local success, message = lib.callback.await('advance-manager:withdrawFunds', false, businessId, input[1])
                    
                    if success then
                        lib.notify({
                            title = 'Success',
                            description = message,
                            type = 'success'
                        })
                        ShowFinancialManagementMenu(businessId)
                    else
                        lib.notify({
                            title = 'Error',
                            description = message or 'Failed to withdraw funds',
                            type = 'error'
                        })
                    end
                end
            end
        }
    }
    
    lib.registerContext({
        id = 'financial_management',
        title = 'Financial Management',
        options = options
    })
    
    lib.showContext('financial_management')
end

-- Commands
lib.addCommand('createbusiness', {
    help = 'Create a new business (Admin only)',
    restricted = 'group.admin'
}, function(source, args, raw)
    ShowCreateBusinessMenu()
end)

lib.addCommand('businessmenu', {
    help = 'Open business management menu'
}, function(source, args, raw)
    ShowBusinessManagementMenu()
end)

print('[advance-manager] Client initialized successfully')
