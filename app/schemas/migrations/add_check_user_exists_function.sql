-- ============================================================================
-- Fonction sécurisée pour vérifier l'existence d'un compte utilisateur par e-mail
-- Utilisée par l'API backend pour valider un e-mail avant l'envoi de réinitialisation
-- ============================================================================

CREATE OR REPLACE FUNCTION public.check_user_exists_by_email(user_email text)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, auth
AS $$
BEGIN
  RETURN EXISTS (
    SELECT 1 
    FROM auth.users 
    WHERE lower(email) = lower(trim(user_email))
  );
END;
$$;

-- Autoriser l'appel de cette fonction RPC via l'API Supabase
GRANT EXECUTE ON FUNCTION public.check_user_exists_by_email(text) TO anon, authenticated, service_role;

