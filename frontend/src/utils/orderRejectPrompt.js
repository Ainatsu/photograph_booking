import { ElMessageBox } from 'element-plus'

const MAX_REJECTION_REASON_LENGTH = 500

export async function promptRejectReason() {
  const { value } = await ElMessageBox.prompt(
    '请填写拒绝原因，客户会在订单详情中看到。建议引导客户重新选时间、联系摄影师或查看其他方案。',
    '拒绝预约',
    {
      confirmButtonText: '确认拒绝',
      cancelButtonText: '取消',
      inputType: 'textarea',
      inputPlaceholder: '例如：该时间段已有拍摄安排，建议重新选择下周工作日下午。',
      inputValidator: (input) => {
        const reason = (input || '').trim()
        if (!reason) return '拒绝订单必须填写原因'
        if (reason.length > MAX_REJECTION_REASON_LENGTH) {
          return `拒绝原因不能超过 ${MAX_REJECTION_REASON_LENGTH} 字`
        }
        return true
      },
      inputErrorMessage: '拒绝订单必须填写原因',
      type: 'warning',
    },
  )

  return value.trim()
}
