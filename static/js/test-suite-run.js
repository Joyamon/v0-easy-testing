/**
 * 测试套件运行页面的增强功能
 */
document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("runForm")
  const defaultEnvironmentSelect = document.getElementById("defaultEnvironment")
  const caseEnvironmentSelects = document.querySelectorAll(".case-environment")

  // 存储键名
  const STORAGE_KEYS = {
    defaultEnvironment: "test_suite_default_environment",
    caseEnvironments: "test_suite_case_environments",
  }

  // 更新环境指示器
  function updateEnvironmentIndicators() {
    caseEnvironmentSelects.forEach((select) => {
      const caseId = select.dataset.caseId
      const indicator = document.getElementById(`env-indicator-${caseId}`)

      if (!indicator) return

      if (select.value) {
        const selectedOption = select.options[select.selectedIndex]
        indicator.innerHTML = `<i class="bi bi-info-circle text-primary"></i> 将使用 <strong>${selectedOption.textContent}</strong> 环境`
        indicator.classList.add("text-primary")
      } else {
        indicator.innerHTML = `<i class="bi bi-arrow-up"></i> 将使用默认环境`
        indicator.classList.add("text-muted")
      }
    })
  }

  // 加载保存的环境选择
  function loadSavedEnvironments() {
    // 加载默认环境
    const savedDefaultEnv = localStorage.getItem(STORAGE_KEYS.defaultEnvironment)
    if (savedDefaultEnv) {
      defaultEnvironmentSelect.value = savedDefaultEnv
    }

    // 加载测试用例环境
    const savedCaseEnvs = localStorage.getItem(STORAGE_KEYS.caseEnvironments)
    if (savedCaseEnvs) {
      try {
        const caseEnvs = JSON.parse(savedCaseEnvs)
        caseEnvironmentSelects.forEach((select) => {
          const caseId = select.dataset.caseId
          if (caseEnvs[caseId]) {
            select.value = caseEnvs[caseId]
          }
        })

        // 更新环境指示器
        updateEnvironmentIndicators()
      } catch (e) {
        console.warn("Failed to parse saved case environments:", e)
      }
    }
  }

  // 保存环境选择
  function saveEnvironments() {
    // 保存默认环境
    if (defaultEnvironmentSelect.value) {
      localStorage.setItem(STORAGE_KEYS.defaultEnvironment, defaultEnvironmentSelect.value)
    }

    // 保存测试用例环境
    const caseEnvs = {}
    caseEnvironmentSelects.forEach((select) => {
      const caseId = select.dataset.caseId
      if (select.value) {
        caseEnvs[caseId] = select.value
      }
    })
    localStorage.setItem(STORAGE_KEYS.caseEnvironments, JSON.stringify(caseEnvs))

    // 更新环境指示器
    updateEnvironmentIndicators()
  }

  // 环境选择变化时
  defaultEnvironmentSelect.addEventListener("change", saveEnvironments)

  // 测试用例环境选择变化时
  caseEnvironmentSelects.forEach((select) => {
    select.addEventListener("change", saveEnvironments)
  })

  // 表单提交前验证
  form.addEventListener("submit", (e) => {
    // 确保表单提交时包含所有必要的环境参数
    const formData = new FormData(form)

    // 检查是否有选择默认环境
    if (!formData.get("environment")) {
      e.preventDefault()
      alert("请选择默认环境")
      defaultEnvironmentSelect.focus()
      return
    }

    // 添加调试信息
    console.log("提交表单数据:")
    for (const [key, value] of formData.entries()) {
      console.log(`${key}: ${value}`)
    }

    // 显示加载状态
    const submitBtn = e.submitter
    submitBtn.disabled = true
    submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>执行中...'

    // 添加隐藏字段，标记表单已验证
    const validatedField = document.createElement("input")
    validatedField.type = "hidden"
    validatedField.name = "form_validated"
    validatedField.value = "true"
    form.appendChild(validatedField)
  })

  // 页面加载时初始化
  loadSavedEnvironments()
  updateEnvironmentIndicators()

  // 添加环境选择提示
  const envHelp = document.createElement("div")
  envHelp.className = "alert alert-info mt-3"
  envHelp.innerHTML = `
        <h5><i class="bi bi-info-circle-fill me-2"></i>环境选择说明</h5>
        <p>您可以为每个测试用例选择不同的环境：</p>
        <ul>
            <li>默认情况下，所有测试用例将使用上方选择的<strong>默认环境</strong></li>
            <li>如果为某个测试用例选择了<strong>个别环境</strong>，则该测试用例将使用指定的环境</li>
            <li>您的环境选择将被保存，下次访问时自动恢复</li>
        </ul>
    `

  // 将提示添加到页面
  const tableContainer = document.querySelector(".table-responsive")
  if (tableContainer) {
    tableContainer.parentNode.insertBefore(envHelp, tableContainer)
  }
})
