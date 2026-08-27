import type { ButtonHTMLAttributes } from 'react'
import './Button.css'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
    variant?: 'primary' | 'secondary' | 'ghost'
}

export function Button({ variant = 'secondary', className, ...rest }: ButtonProps) {
    return <button className={`btn btn--${variant} ${className ?? ''}`} {...rest} />
}
