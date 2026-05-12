import { Button } from "@/components/ui/button";

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 p-8">
      <h1 className="text-4xl font-semibold tracking-tight">ReviewMaster</h1>
      <p className="text-muted-foreground max-w-md text-center">
        Skeleton up and running. Real features arrive in the next stages.
      </p>
      <Button>It works</Button>
    </main>
  );
}
