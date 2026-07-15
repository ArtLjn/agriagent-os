import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Form } from 'antd';

import TemplateForm from './TemplateForm';

describe('TemplateForm', () => {
  it('渲染名称、品种和生长阶段输入区', () => {
    render(
      <Form>
        <TemplateForm />
      </Form>,
    );

    expect(screen.getByText('名称')).toBeInTheDocument();
    expect(screen.getByText('品种')).toBeInTheDocument();
    expect(screen.getByText('生长阶段')).toBeInTheDocument();
  });

  it('初始阶段数由表单 initialValues 控制', () => {
    render(
      <Form initialValues={{ stages: [{ name: '', duration_days: 1, key_tasks: '' }] }}>
        <TemplateForm />
      </Form>,
    );

    expect(screen.getAllByPlaceholderText('阶段名').length).toBe(1);
  });

  it('未设置 initialValues 时默认无阶段行，但有添加按钮', () => {
    render(
      <Form>
        <TemplateForm />
      </Form>,
    );

    expect(screen.queryAllByPlaceholderText('阶段名').length).toBe(0);
    expect(screen.getByRole('button', { name: /添加阶段/ })).toBeInTheDocument();
  });
});
