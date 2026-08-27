import './SectionHeading.css'

interface SectionHeadingProps {
    eyebrow?: string
    title: string
    description?: string
}

export function SectionHeading({ eyebrow, title, description }: SectionHeadingProps) {
    return (
        <div className="section-heading">
            {eyebrow && <p className="section-heading__eyebrow">{eyebrow}</p>}
            <h1 className="section-heading__title">{title}</h1>
            {description && <p className="section-heading__description">{description}</p>}
        </div>
    )
}
