import { toaster } from "@/components/ui/toaster";
import { describeError } from "@/store/api";

type ToastMutationOptions<T> = {
  loading?: string;
  success?: string | ((data: T) => string);
  errorTitle?: string;
};

/**
 * Universal toaster.promise wrapper for RTK Query `.unwrap()` promises.
 * loading → success / error (description from API ErrorBody message + fields).
 */
export async function toastMutation<T>(
  promise: Promise<T>,
  options: ToastMutationOptions<T> = {},
): Promise<T> {
  const tracked = toaster.promise(promise, {
    loading: { title: options.loading ?? "Working…" },
    success: (data) => ({
      title:
        typeof options.success === "function"
          ? options.success(data)
          : (options.success ?? "Done"),
    }),
    error: (err) => ({
      title: options.errorTitle ?? "Error",
      description: describeError(err),
      meta: { closable: true },
    }),
  });
  if (tracked?.unwrap) {
    return tracked.unwrap();
  }
  return promise;
}
