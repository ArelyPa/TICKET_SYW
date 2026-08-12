import { useState } from 'react'
import { App, Button, Divider, Form, Input, Modal, Segmented } from 'antd'
import { GoogleOutlined, LockOutlined, MailOutlined, TeamOutlined, UserOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import { authService, type LoginMode } from '../services/authService'
import AuthLayout from '../components/common/AuthLayout'
import { palette } from '../theme'

interface LoginFormValues {
  username_or_email: string
  password: string
}

// Acento por modo de login: terracota (color primario ya usado en toda la app) para
// Equipo, teal (ya usado como "oficial"/institucional en el calendario, spec 021) para
// Portal Cliente — refuerza qué puerta está activa sin introducir colores nuevos.
const MODE_ACCENT: Record<LoginMode, string> = {
  team: palette.brandOrange500,
  client_portal: palette.teal600,
}

export default function LoginPage() {
  const navigate = useNavigate()
  const { setAuth, isAuthenticated } = useAuthStore()
  // OBS-0044: la instancia estática `message` de 'antd' no renderiza ningún toast en esta
  // app (mismo síntoma que OBS-0029/spec 028) — se usa la instancia ligada al `<App>` de antd.
  const { message } = App.useApp()
  const [loading, setLoading] = useState(false)
  const [forgotOpen, setForgotOpen] = useState(false)
  const [forgotLoading, setForgotLoading] = useState(false)
  const [forgotForm] = Form.useForm<{ email: string }>()
  // spec 046 (FR-001): "Equipo" seleccionada por defecto (Acceptance Scenario 1).
  const [loginMode, setLoginMode] = useState<LoginMode>('team')

  if (isAuthenticated()) {
    navigate('/dashboard', { replace: true })
  }

  const handleForgotPassword = async ({ email }: { email: string }) => {
    setForgotLoading(true)
    try {
      const { message: msg } = await authService.forgotPassword(email)
      message.success(msg)
      setForgotOpen(false)
      forgotForm.resetFields()
    } catch {
      message.error('No se pudo procesar la solicitud, intenta de nuevo')
    } finally {
      setForgotLoading(false)
    }
  }

  const handleSubmit = async (values: LoginFormValues) => {
    setLoading(true)
    try {
      const { access_token, user } = await authService.login(
        values.username_or_email, values.password, loginMode)
      setAuth(access_token, user)
      navigate('/dashboard', { replace: true })
    } catch (err: unknown) {
      const response = (err as { response?: { data?: { message?: string } } }).response
      if (!response) {
        message.error('No se pudo conectar, intenta de nuevo')
      } else {
        message.error(response.data?.message ?? 'Usuario o contraseña incorrectos')
      }
    } finally {
      setLoading(false)
    }
  }

  const handleGoogleLogin = () => {
    // Integración real de Google Identity Services pendiente (requiere GOOGLE_CLIENT_ID
    // configurado en el entorno). El endpoint backend /api/auth/google ya está listo.
    message.info('Login con Google pendiente de configurar en este entorno — usa usuario y contraseña.')
  }

  return (
    <AuthLayout
      title="Iniciar sesión"
      subtitle={loginMode === 'team' ? 'Usa tu cuenta @sywork.net' : 'Ingresa con tu cuenta de cliente'}
      accentColor={MODE_ACCENT[loginMode]}
    >
      <Segmented
        block
        size="large"
        value={loginMode}
        onChange={value => setLoginMode(value as LoginMode)}
        options={[
          { value: 'team', label: (<span><TeamOutlined /> Equipo</span>) },
          { value: 'client_portal', label: (<span><UserOutlined /> Portal Cliente</span>) },
        ]}
        style={{ marginBottom: 24 }}
      />
      <Form layout="vertical" onFinish={handleSubmit} requiredMark={false}>
        <Form.Item
          name="username_or_email"
          label="Correo o usuario"
          rules={[{ required: true, message: 'El correo o usuario es requerido' }]}
        >
          <Input prefix={<UserOutlined />} placeholder="usuario o correo@sywork.net" autoFocus />
        </Form.Item>
        <Form.Item
          name="password"
          label="Contraseña"
          rules={[{ required: true, message: 'La contraseña es requerida' }]}
        >
          <Input.Password prefix={<LockOutlined />} placeholder="Contraseña" />
        </Form.Item>
        <Form.Item style={{ marginBottom: 0 }}>
          <Button
            type="primary" htmlType="submit" block loading={loading}
            style={{ background: MODE_ACCENT[loginMode], borderColor: MODE_ACCENT[loginMode] }}
          >
            Iniciar sesión
          </Button>
        </Form.Item>
      </Form>

      <div style={{ textAlign: 'center', marginTop: 20 }}>
        <Button
          type="link" size="small" onClick={() => setForgotOpen(true)}
          style={{ color: MODE_ACCENT[loginMode] }}
        >
          ¿Olvidaste tu contraseña?
        </Button>
      </div>

      <Divider style={{ margin: '20px 0' }}>o</Divider>

      <Button icon={<GoogleOutlined />} block onClick={handleGoogleLogin}>
        Continuar con Google
      </Button>

      <Modal
        title="Recuperar contraseña"
        open={forgotOpen}
        onCancel={() => setForgotOpen(false)}
        onOk={() => forgotForm.submit()}
        okText="Enviar"
        confirmLoading={forgotLoading}
      >
        <Form form={forgotForm} layout="vertical" onFinish={handleForgotPassword}>
          <Form.Item
            name="email"
            label="Correo @sywork.net"
            rules={[{ required: true, message: 'El correo es requerido' }]}
          >
            <Input prefix={<MailOutlined />} placeholder="correo@sywork.net" autoFocus />
          </Form.Item>
        </Form>
      </Modal>
    </AuthLayout>
  )
}
