import { ArrowLeft, HelpCircle } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { Card, CardBody } from "@/components/ui/card";

export interface HelpViewProps {
  onBack: () => void;
}

interface HelpSection {
  head: string;
  items: string[];
}

/** 帮助页（规范 7.16.9：HelpCircle 跳独立帮助页，底部返回） */
export function HelpView({ onBack }: HelpViewProps) {
  const { t } = useTranslation();
  const sections = (t("help.sections", { returnObjects: true }) as unknown as HelpSection[]) ?? [];

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div className="flex items-center gap-2.5">
        <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-50 dark:bg-brand-900">
          <HelpCircle className="h-5 w-5 text-brand-600 dark:text-brand-300" aria-hidden="true" />
        </span>
        <div>
          <h1 className="text-xl font-bold text-ink-900 dark:text-surface-0">{t("help.title")}</h1>
        </div>
      </div>
      <p className="text-sm leading-6 text-ink-700 dark:text-surface-4">{t("help.intro")}</p>

      {sections.map((sec) => (
        <Card key={sec.head}>
          <CardBody className="pt-6">
            <h2 className="text-base font-semibold text-ink-900 dark:text-surface-0">{sec.head}</h2>
            <ul className="mt-3 list-disc space-y-2 pl-5">
              {(sec.items ?? []).map((item, i) => (
                <li key={i} className="text-sm leading-6 text-ink-700 dark:text-surface-4">
                  {item}
                </li>
              ))}
            </ul>
          </CardBody>
        </Card>
      ))}

      <div className="flex justify-end">
        <Button variant="secondary" icon={<ArrowLeft className="h-4 w-4" aria-hidden="true" />} onClick={onBack}>
          {t("help.back")}
        </Button>
      </div>
    </div>
  );
}
