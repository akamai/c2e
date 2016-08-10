import java.lang.StringBuilder;
import java.io.ByteArrayInputStream;
import java.io.InputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.io.InputStreamReader;
import java.io.BufferedReader;

public class Encode
{

    public static void main (String [] args) throws IOException {
	String str = "<here we > test some & things \u1f47 \u00ff";
	System.out.println(str);
	System.out.println(Encode.forHTML(str));
	System.out.println(Encode.forHTMLAttribute(str));
	System.out.println(Encode.forJavaScriptString(str));
	System.out.println(Encode.forCSS(str));
    }

    /* [[[C2E
       import cog, c2e

       source_code = []
       for codec in c2e.encoder.codecs:
           codec_cog = c2e.C2Ecog(codec=codec, class_name='Encode', suffix='')
           source_code.append(codec_cog('templates/Java/codec.template'))
           source_code.append('\n\n')
       cog.outl(''.join(source_code))

       ]]] /*
    /* [[[END]]] */
    

    // BUILTINS
    
    public static String DEC(int c) {
	return Integer.toString(c);
    }
    
    public static String HEX(int c)
    {
	return Integer.toHexString(c);
    }
    public static String NOP(int c)
    {
	return "";
    }
    public static String IDENTITY(int c)
    {
	return new String(Character.toChars(c));
    }
}
