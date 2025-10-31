QBCore = exports['qb-core']:GetCoreObject()

local PlayerData = QBCore.Functions.GetPlayerData()
local currentBusiness = nil
local groupDigits = lib.math.groupdigits
local deepClone = lib.table.deepclone

local function getBusinessGradeMetadata(business)
    if not business then
        return {}
    end

    local metadata = business.gradeMetadata or business.grade_metadata
    if type(metadata) == 'table' and #metadata > 0 then
        local normalized = {}

        for _, entry in pairs(metadata) do
            if type(entry) == 'table' then
                local gradeValue = tonumber(entry.value or entry.grade)
                if gradeValue then
                    normalized[#normalized + 1] = {
                        grade = gradeValue,
                        label = entry.label or entry.name or ('Grade ' .. gradeValue),
                        wage = tonumber(entry.wage or entry.payment),
                        isboss = entry.isboss and true or false
                    }
                end
            end
        end

        table.sort(normalized, function(a, b)
            return a.grade < b.grade
        end)

        return normalized
    end

    local jobInfo = business.jobInfo or business.job_info
    if type(jobInfo) == 'table' and type(jobInfo.grades) == 'table' then
        local normalized = {}

        for gradeKey, gradeData in pairs(jobInfo.grades) do
            local gradeValue = tonumber(gradeKey)
            if gradeValue then
                normalized[#normalized + 1] = {
                    grade = gradeValue,
                    label = gradeData.label or gradeData.name or ('Grade ' .. gradeValue),
                    wage = tonumber(gradeData.payment),
                    isboss = gradeData.isboss and true or false
                }
            end
        end

        table.sort(normalized, function(a, b)
            return a.grade < b.grade
        end)

        return normalized
    end

    return {}
end

local function getBusinessWageLimits(business)
    local limits = business and (business.wageLimits or business.wage_limits)
    local minWage = 0
    local maxWage = 10000

    if type(limits) == 'table' then
        if tonumber(limits.min) then
            minWage = tonumber(limits.min)
        end
        if tonumber(limits.max) then
            maxWage = tonumber(limits.max)
        end
    end

    return minWage, maxWage
end

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

    local canOpen, errorMessage = lib.callback.await('advance-manager:canCreateBusiness', false)

    if not canOpen then
        lib.notify({
            title = 'Unavailable',
            description = errorMessage or 'You do not have permission to create businesses',
            type = 'error'
        })
        return
    end

    local availableJobs, jobsError = lib.callback.await('advance-manager:getAvailableJobs', false)

    if not availableJobs then
        lib.notify({
            title = 'Error',
            description = jobsError or 'Failed to load available jobs',
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
    local gradeMetadata = getBusinessGradeMetadata(currentBusiness)
    local wageMin, wageMax = getBusinessWageLimits(currentBusiness)
    local gradeOptions = {}
    local gradeToWage = {}
    local gradeMin, gradeMax = nil, nil
    local defaultGradeKey = nil

    for _, gradeInfo in ipairs(gradeMetadata) do
        local gradeValue = gradeInfo.grade
        local wageDisplay = gradeInfo.wage and groupDigits(gradeInfo.wage) or '0'
        local optionLabel = ('Grade %d - %s ($%s/hr)'):format(gradeValue, gradeInfo.label, wageDisplay)
        table.insert(gradeOptions, {value = tostring(gradeValue), label = optionLabel})
        gradeToWage[tostring(gradeValue)] = gradeInfo.wage
        gradeMin = gradeMin and math.min(gradeMin, gradeValue) or gradeValue
        gradeMax = gradeMax and math.max(gradeMax, gradeValue) or gradeValue
        defaultGradeKey = defaultGradeKey or tostring(gradeValue)
    end

    if not gradeMin or not gradeMax then
        local jobInfo = currentBusiness and (currentBusiness.jobInfo or currentBusiness.job_info)
        if jobInfo and type(jobInfo.grades) == 'table' then
            for gradeKey in pairs(jobInfo.grades) do
                local numericGrade = tonumber(gradeKey)
                if numericGrade then
                    gradeMin = gradeMin and math.min(gradeMin, numericGrade) or numericGrade
                    gradeMax = gradeMax and math.max(gradeMax, numericGrade) or numericGrade
                end
            end
        end
    end

    gradeMin = gradeMin or 0
    gradeMax = gradeMax or gradeMin

    local fields = {
        {type = 'number', label = 'Player ID', placeholder = 'Enter player ID to hire', required = true}
    }

    local gradeFieldIndex = #fields + 1
    if #gradeOptions > 0 then
        fields[#fields + 1] = {type = 'select', label = 'Grade', options = gradeOptions, required = true, default = defaultGradeKey}
    else
        fields[#fields + 1] = {type = 'number', label = 'Grade', placeholder = ('Enter job grade (%d-%d)'):format(gradeMin, gradeMax), required = true, min = gradeMin, max = gradeMax}
    end

    local input = lib.inputDialog('Hire Employee', fields)

    if input then
        local playerId = tonumber(input[1])
        local gradeInput = input[gradeFieldIndex]

        if not playerId or playerId <= 0 then
            lib.notify({
                title = 'Error',
                description = 'Please enter a valid player ID',
                type = 'error'
            })
            return
        end

        local gradeValue = tonumber(gradeInput)
        if not gradeValue then
            lib.notify({
                title = 'Error',
                description = 'Invalid grade selected',
                type = 'error'
            })
            return
        end

        if gradeValue < gradeMin or gradeValue > gradeMax then
            lib.notify({
                title = 'Error',
                description = ('Grade must be between %d and %d'):format(gradeMin, gradeMax),
                type = 'error'
            })
            return
        end

        if #gradeOptions > 0 and not gradeToWage[tostring(gradeValue)] then
            lib.notify({
                title = 'Error',
                description = 'Selected grade is not available for this business',
                type = 'error'
            })
            return
        end

        local assignedWage = gradeToWage[tostring(gradeValue)]
        if not assignedWage then
            assignedWage = wageMin
        end

        assignedWage = math.max(wageMin, math.min(assignedWage, wageMax))

        local success, message = lib.callback.await('advance-manager:hireEmployee', false, businessId, playerId, gradeValue, assignedWage)

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
    local gradeMetadata = getBusinessGradeMetadata(currentBusiness)
    local wageMin, wageMax = getBusinessWageLimits(currentBusiness)
    local gradeOptions = {}
    local gradeLookup = {}
    local gradeMin, gradeMax = nil, nil

    for _, gradeInfo in ipairs(gradeMetadata) do
        local wageDisplay = gradeInfo.wage and groupDigits(gradeInfo.wage) or '0'
        local optionLabel = ('Grade %d - %s ($%s/hr)'):format(gradeInfo.grade, gradeInfo.label, wageDisplay)
        table.insert(gradeOptions, {value = tostring(gradeInfo.grade), label = optionLabel})
        gradeLookup[tostring(gradeInfo.grade)] = gradeInfo
        gradeMin = gradeMin and math.min(gradeMin, gradeInfo.grade) or gradeInfo.grade
        gradeMax = gradeMax and math.max(gradeMax, gradeInfo.grade) or gradeInfo.grade
    end

    if not gradeMin or not gradeMax then
        local jobInfo = currentBusiness and (currentBusiness.jobInfo or currentBusiness.job_info)
        if jobInfo and type(jobInfo.grades) == 'table' then
            for gradeKey in pairs(jobInfo.grades) do
                local numericGrade = tonumber(gradeKey)
                if numericGrade then
                    gradeMin = gradeMin and math.min(gradeMin, numericGrade) or numericGrade
                    gradeMax = gradeMax and math.max(gradeMax, numericGrade) or numericGrade
                end
            end
        end
    end

    gradeMin = gradeMin or 0
    gradeMax = gradeMax or gradeMin

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
                    {type = 'number', label = 'New Wage', placeholder = 'Enter new wage', required = true, min = wageMin, max = wageMax, default = employee.wage}
                })

                if input then
                    local wageValue = tonumber(input[1])

                    if not wageValue or wageValue < wageMin or wageValue > wageMax then
                        lib.notify({
                            title = 'Error',
                            description = ('Wage must be between %s and %s'):format(groupDigits(wageMin), groupDigits(wageMax)),
                            type = 'error'
                        })
                        return
                    end

                    local success = lib.callback.await('advance-manager:updateEmployeeWage', false, businessId, employee.citizenid, wageValue)

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
                local input

                if #gradeOptions > 0 then
                    input = lib.inputDialog('Update Grade', {
                        {type = 'select', label = 'New Grade', options = gradeOptions, required = true, default = tostring(employee.grade)}
                    })
                else
                    input = lib.inputDialog('Update Grade', {
                        {type = 'number', label = 'New Grade', placeholder = ('Enter new grade (%d-%d)'):format(gradeMin, gradeMax), required = true, min = gradeMin, max = gradeMax, default = employee.grade}
                    })
                end

                if input then
                    local gradeValue = tonumber(input[1])

                    if not gradeValue or gradeValue < gradeMin or gradeValue > gradeMax then
                        lib.notify({
                            title = 'Error',
                            description = ('Grade must be between %d and %d'):format(gradeMin, gradeMax),
                            type = 'error'
                        })
                        return
                    end

                    if #gradeOptions > 0 and not gradeLookup[tostring(gradeValue)] then
                        lib.notify({
                            title = 'Error',
                            description = 'Selected grade is not available for this business',
                            type = 'error'
                        })
                        return
                    end

                    local success = lib.callback.await('advance-manager:updateEmployeeGrade', false, businessId, employee.citizenid, gradeValue)

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

RegisterNetEvent('advance-manager:client:openCreateBusinessMenu', function()
    ShowCreateBusinessMenu()
end)

RegisterNetEvent('advance-manager:client:openBusinessManagementMenu', function()
    ShowBusinessManagementMenu()
end)

print('[advance-manager] Client initialized successfully')
